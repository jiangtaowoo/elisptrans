# -*- coding: utf-8 -*-
import os
from sys import argv
import re
import json
import copy
import lxml.html
import datetime
import yaml
from collections import deque
import requests
from requests.models import Response as ReqResponse
import baidufy_sign
import ormadaptor
import gevent
from gevent import monkey
monkey.patch_all()

"""
翻译结果结构体
"""
class WordTranslateResult(object):
    __attrs__ = [
        'word', 'wordem', 'ph_am', 'ph_en', 'tags',
        'word_third', 'word_done', 'word_pl', 'word_est', 'word_ing',
        'word_er', 'word_past', 'mean', 'sentence', 'basicmean', 'means', 'enmeans', 'vocabulary'
    ]
    __iterable_attrs__ = ['basicmean', 'means', 'enmeans']
    __exchange_attrs__ = {'word_third': u'第三人称单数', 'word_done': u'过去分词',
                        'word_pl': u'复数', 'word_est': u'EST',
                        'word_ing': u'现在分词', 'word_er': u'ER',
                        'word_past': u'过去式'
    }

    def __init__(self):
        self.ada = ormadaptor.AdaptorORM('dictmodel.yaml', 'vocabulary.db')
        self.vocabulary = ""   #vocabulary网站的解释
        self.word = ""         #单词本身
        self.wordem = ""       #读音分隔, 重音在哪
        self.ph_am = ""        #美式音标
        self.ph_en = ""        #英式音标
        self.tags = ""         #TAGS, 例如CET6等
        self.word_third = ""   #第三人称形态
        self.word_done = ""    #完成时态
        self.word_pl = ""      #pl
        self.word_est = ""     #est
        self.word_ing = ""     #进行时态
        self.word_er = ""      #er
        self.word_past = ""    #过去式
        self.mean = ""         #基本释义
        self.sentence = ""     #上下文句子
        self.basicmean = []    #词性, 词义
        self.means = dict()    #单词释义及例句
        #self.means['oxford'] = [{'en':'','zh':''},{'en':'', 'zh':''}]
        self.enmeans = []      #英文释义
        #[{'noun':[{tr, example, similar_word},{}]}]

    #vocabulary结果
    def parse_vocabulary_result_from_rsp(self, rsp):
        def flashcard_format(s):
            return s.replace('\n','<br>').replace('\t',' ')
        def _stringify_node(node):
            parts = ([x for x in node.itertext()])
            return flashcard_format(''.join(filter(None, parts)).strip())
        if isinstance(rsp, ReqResponse) and rsp.status_code==200:
            html = lxml.html.fromstring(rsp.text)
            main_divs = html.xpath("//div[@class='section blurb']")
            v = []
            if main_divs:
                v.append(u"<div>{0}</div>".format(_stringify_node(main_divs[0])))
            definiction_divs = html.xpath("//div[@class='main']/div[@class='definitions']/div")
            if definiction_divs:
                v.append(u"<div>{0}</div>".format(_stringify_node(definiction_divs[0])))
            self.vocabulary = ' '.join(v)
            return True
        else:
            return None

    #从响应结构体中提取翻译结果
    def parse_result_from_rsp(self, rsp):
        if isinstance(rsp, ReqResponse):
            htmlText = rsp.text
        else:
            htmlText = rsp
        try:
            jsondata = json.loads(htmlText)
            self._extract_basic(jsondata)
            self._extract_endict(jsondata)
            self._extract_oxford(jsondata)
            self._extract_collins(jsondata)
            if self.word and self.mean:
                return True
            return None
        except Exception as e:
            print "parse rsp except %s" % (e)
            return None

    #提取基本翻译信息
    def _extract_basic(self, jsondata):
        try:
            self.word = jsondata['trans_result']['data'][0]['src']
            self.mean = jsondata['trans_result']['data'][0]['dst']
            if 'dict_result' in jsondata:
                jsonx = jsondata['dict_result']
                if 'collins' in jsonx and 'word_emphasize' in jsonx['collins']:
                    self.wordem = jsonx['collins']['word_emphasize'].replace('|','.')
                if 'simple_means' in jsonx:
                    jsonx = jsonx['simple_means']
                    if 'exchange' in jsonx:
                        x = jsonx['exchange']
                        for attr in self.__attrs__:
                            if attr in x and isinstance(x[attr],list) and x[attr]:
                                setattr(self, attr, x[attr][0])
                    if 'tags' in jsonx:
                        self.tags = []
                        self.tags.extend(jsonx['tags']['core'])
                        self.tags.extend(jsonx['tags']['other'])
                        self.tags = ','.join(filter(len,self.tags))
                    if 'symbols' in jsonx:
                        jsonx = jsonx['symbols']
                        if isinstance(jsonx,list) and len(jsonx)>0:
                            jsonx = jsonx[0]
                            self.ph_am = jsonx['ph_am'] if 'ph_am' in jsonx else ""
                            self.ph_en = jsonx['ph_en'] if 'ph_en' in jsonx else ""
                            if 'parts' in jsonx:
                                jsonx = jsonx['parts']
                                for x in jsonx:
                                    if 'part' in x and 'means' in x:
                                        self.basicmean.append({'posp': x['part'],
                                                               'mean':';'.join(x['means'])})
        except:
            pass

    #提取英文释义
    def _extract_endict(self, jsondata):
        try:
            if 'dict_result' in jsondata:
                jsonx = jsondata['dict_result']
                if 'edict' in jsonx and 'item' in jsonx['edict']:
                    jsonx = jsonx['edict']['item']
                    if jsonx:
                        for posjsonx in jsonx:
                            if 'pos' in posjsonx and 'tr_group' in posjsonx:
                                self.enmeans.append({posjsonx['pos']: posjsonx['tr_group']})
        except:
            pass

    #提取牛津词典释义
    def _extract_oxford(self, jsondata):
        #递归查找每个dict项, 如果其仍然包含data子项, 递归下去
        def _iter_extract_data_ox(data, result):
            #1. 先获取当前范围的数据
            res = None
            if 'enText' in data:
                res = {'en': data['enText']}
            if 'chText' in data and res:
                res['zh'] = data['chText']
            if res:
                result.append(res)
            if 'data' in data and isinstance(data['data'], list) and data['data']:
                for d in data['data']:
                    if isinstance(d, dict):
                        _iter_extract_data_ox(d, result)
        try:
            if 'dict_result' in jsondata:
                jsonx = jsondata['dict_result']
                if 'oxford' in jsonx and 'entry' in jsonx['oxford']:
                    self.means['oxford'] = []
                    jsonx = jsonx['oxford']['entry']
                    for data in jsonx:
                        if isinstance(data, dict):
                            _iter_extract_data_ox(data, self.means['oxford'])
        except:
            pass

    #提取柯林斯词典释义
    def _extract_collins(self, jsondata):
        try:
            if 'dict_result' in jsondata:
                jsonx = jsondata['dict_result']
                if 'collins' in jsonx and 'entry' in jsonx['collins']:
                    self.means['collins'] = []
                    jsonx = jsonx['collins']['entry']
                    for data in jsonx:
                        if isinstance(data, dict):
                            if 'value' in data:
                                data = data['value']
                                for d in data:
                                    res = None
                                    if 'def' in d:
                                        res = {'en': d['def']}
                                    if 'tran' in d and res:
                                        res['zh'] = d['tran']
                                    if res:
                                        self.means['collins'].append(res)
                                    if 'mean_type' in d:
                                        for dm in d['mean_type']:
                                            if 'example' in dm:
                                                for ex in dm['example']:
                                                    resx = None
                                                    if 'ex' in ex:
                                                        resx = {'en': ex['ex']}
                                                    if 'tran' in ex and resx:
                                                        resx['zh'] = ex['tran']
                                                    if resx:
                                                        self.means['collins'].append(resx)
        except:
            pass

    #从数据库读取信息
    def read_result_from_db(self, word):
        return self.export_db({'word': word})

    #生成SQLite格式的结果数据, 向数据库写数据
    def write_result_to_db(self):
        def encap_data(x):
            if isinstance(x,list) or isinstance(x,dict):
                return json.dumps(x)
            return x
        db_fields_data = dict(
            (attr, encap_data(getattr(self, attr, "")))
            for attr in self.__attrs__)
        if self.word and self.mean:
            if not self.ada.exists(**db_fields_data):
                self.ada.save(**db_fields_data)
            #else:
            #    self._exclude_pk_data(modelname)
            #    self._persist_adaptor.update_data(modelname, modelcfg, self._pk_data, **self._fields_data)

    #导出满足筛选条件的SQLite数据
    def export_db(self, filters, filename=None):
        #筛选条件为k,v格式, 例如  tags='%CET4%', 会筛选 tags列包含CET4的数据, 条件为与关系
        def uncap_data(attr, x):
            if attr in self.__iterable_attrs__:
                return json.loads(x)
            return x
        def set_datarow(fieldnames, datarow):
            for idx, field in enumerate(fieldnames):
                if field in self.__attrs__:
                    setattr(self, field, uncap_data(field, datarow[idx]))
        #查询数据库
        (fieldnames, dataset) = self.ada.load(**filters)
        if filename and dataset:
            with open(filename, 'a+') as outf:
                for datarow in dataset:
                    set_datarow(fieldnames, datarow)
                    outf.write(self.gen_flashcard_format().encode('utf-8'))
                    outf.write('\n')
            return True
        elif dataset:
            datarow = dataset[0]
            set_datarow(fieldnames, datarow)
            return True
        return False


    #生成FlashCard格式的结果数据, 一行数据, 允许使用HTML标识
    def gen_flashcard_format(self):
        front = self.word
        sepc = '  '    #列分隔符
        sepr = '<br>'  #行分隔符
        #卡片反面
        back = []
        #第零行, 原文上下文对应的句子
        if self.sentence:
            if not isinstance(self.sentence, unicode):
                self.sentence = unicode(self.sentence, "utf-8")
            back.append(self.sentence.replace('\r',' ').replace('\n',' ').replace(self.word, '<b>'+self.word+'</b>')+'<hr>')
        #第一行, 读音分隔, 音标, 基本释义
        (wordem, ph_am, ph_en) = ('', '', '')
        if self.wordem:
            wordem = ''.join(['<b style="color:red">', self.wordem, '</b>'])
        if self.ph_am:
            ph_am = ''.join([u'美', ' [', self.ph_am, ']'])
        if self.ph_en:
            ph_en = ''.join([u'英', ' [', self.ph_en, ']'])
        l = filter(len,[wordem, ph_am, ph_en, '<b>'+self.mean+'</b>', '<br>'])
        back.append(sepc.join(l))
        #第二行, 词形变换
        l = []
        for attr, attrzh in self.__exchange_attrs__.iteritems():
            v = getattr(self, attr, "")
            if v:
                l.append( attrzh + ':' + v)
        back.append(sepc.join(l))
        #第三行, tags
        if self.tags:
            back.append(self.tags.replace(',', sepc))
        #第3.5行, vocabulary
        if self.vocabulary:
            if not isinstance(self.vocabulary, unicode):
                self.vocabulary = unicode(self.vocabulary, "utf-8")
            vocab_v = re.sub(r'(<br>\s*)+', '<br>', self.vocabulary)
            if '</div> <div>' in vocab_v:
                vocab_v = vocab_v[:vocab_v.index('</div> <div>')+6]
            back.append('<hr>' + vocab_v.replace('\r',' ').replace('\n',' ').replace('\t', ' ').replace(self.word, '<b>'+self.word+'</b>') + '<hr>')
        #第四行, 基本词义, 含词性 basicmean, 每条解释占一行
        if self.basicmean:
            for bmean in self.basicmean:
                back.append(sepc.join([bmean['posp'], bmean['mean']]))
        #第五行, 各词典解释及例句
        if self.means:
            dictname = {'oxford': u'<br>牛津词典<hr>',
                        'collins': u'<br>柯林斯词典<hr>'}
            for dname, dmeans in self.means.iteritems():
                if dname in dictname:
                    back.append(dictname[dname])
                    for m in dmeans:
                        if 'en' in m:
                            back.append(m['en'])
                        if 'zh' in m:
                            back.append(m['zh'])
        #第六行, 英文释义
        if self.enmeans:
            for dmeans in self.enmeans:
                for posp, enmeanlist in dmeans.iteritems():
                    back.append('<br><b>' + posp + '</b>')
                    for idx, enx in enumerate(enmeanlist):
                        if 'tr' in enx and enx['tr']:
                            x = '; '.join(enx['tr'])
                            back.append( str(idx+1)+'. '+x)
                        if 'example' in enx and enx['example']:
                            for x in enx['example']:
                                back.append('    ' + x)
                        if 'similar_word' in enx and enx['similar_word']:
                            x = '; '.join(enx['similar_word'])
                            back.append('    similar: '+x)
        #合成卡片内容
        return front + '\t' + sepr.join(back)


"""
翻译方法, 调用网络翻译内容, 解析结果
"""
class BDTranslation(object):
    @staticmethod
    def _init_request(sess, req_dict, js_dict):
        cookie_dict = {'locale': 'zh', 'BAIDUID': '84714D78F6D00E5CF202E62D0D643143:FG=1'}
        sess.cookies = requests.utils.cookiejar_from_dict(cookie_dict)
        url = 'https://fanyi.baidu.com'
        headers = {'Host': 'fanyi.baidu.com', 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/63.0.3239.84 Chrome/63.0.3239.84 Safari/537.36', 'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate', 'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8','Connection': 'keep-alive', 'Referer': 'https://fanyi.baidu.com/', 'X-Requested-With': 'XMLHttpRequest'}
        req_dict['url'] = url
        req_dict['headers'] = headers
        try:
            rsp = sess.get(**req_dict)
            return BDTranslation._parse_jsvar(rsp, js_dict)
        except:
            return False

    @staticmethod
    def _parse_jsvar(rsp, js_dict):
        if isinstance(rsp, ReqResponse):
            htmlText = rsp.text
        else:
            htmlText = rsp
        try:
            if isinstance(js_dict, dict):
                idx1 = htmlText.index('window.gtk')
                window_gtk = str(htmlText[idx1:idx1+50].split(';')[0].split('=')[1].strip().replace("'",''))
                idx2 = htmlText.index('token:')
                token = str(htmlText[idx2:idx2+50].split(',')[0].split(':')[1].strip().replace("'",""))
                js_dict['token'] = str(token)
                js_dict['gtk'] = str(window_gtk)
                return True
            else:
                return False
        except:
            return False

    @staticmethod
    def _gen_payload(word, js_dict, srclang):
        token = js_dict['token']
        window_gtk = js_dict['gtk']
        sign = baidufy_sign.calc_sign(word, window_gtk)
        payload = dict()
        payload['from'] = srclang
        payload['to'] = 'en' if srclang=='zh' else 'zh'
        payload['query'] = word
        payload['simple_means_flag'] = '3'
        payload['sign'] = sign
        payload['token'] = token
        payload['transtype'] = 'realtime'
        return payload

    @staticmethod
    def _translate_request(sess, req_dict, js_dict, word, sentence, srclang):
        word_obj = WordTranslateResult()
        word_obj.sentence = sentence.replace('\r',' ').replace('\n',' ')
        word_in_dict = word_obj.read_result_from_db(word)
        if not word_in_dict:
            urlapi = 'https://fanyi.baidu.com/v2transapi'
            #step 1. first visit, to get gtk, token
            if not BDTranslation._init_request(sess, req_dict, js_dict):
                return None
            #step 2. visit translate api
            try:
                tran_results = dict()
                #req_dict = copy.deepcopy(req_dict)
                #vocabulary.com
                req_dict0 = {"url": "https://www.vocabulary.com", "headers": {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:63.0) Gecko/20100101 Firefox/63.0', 'Host':'www.vocabulary.com', 'Referer': 'https://www.vocabulary.com/dictionary/'}}
                rsp0 = sess.get(**req_dict0)
                req_dict0['url'] = 'https://www.vocabulary.com/dictionary/definition.ajax'
                req_dict0['params'] = {"search": word, "lang": "en"}
                rsp0 = sess.get(**req_dict0)
                res0 = word_obj.parse_vocabulary_result_from_rsp(rsp0)
                if not res0:
                    return None
                #fanyi.baidu
                req_dict['url'] = urlapi
                req_dict['data'] = BDTranslation._gen_payload(word, js_dict, srclang)
                rsp = sess.post(**req_dict)
                res = word_obj.parse_result_from_rsp(rsp)
                if res:
                    word_obj.write_result_to_db()
                    return word_obj.gen_flashcard_format()
                else:
                    return None
            except Exception as e:
                print "translate_req except %s" % (e)
                return None
        else:
            return word_obj.gen_flashcard_format()

    def translate_worker(self, workerid, params):
        while self.words_tobe_t:
            line, word = self.words_tobe_t.popleft()
            if word:
                params['word'] = word
                result = BDTranslation._translate_request(**params)
                if not result:
                    print('****** Worker {0} failed on line {1}: {2} ...'.format(workerid, line, word))
                    gevent.sleep(5)
                else:
                    print('Woker {0} is traslate line {1} successful: {2}...'.format(workerid, line, word))
            else:
                gevent.sleep(0)
        print('worker %d is quiting ...').format(workerid)

    @staticmethod
    def _detect_lang(word):
        if ord(word[0])>122:
            return 'zh'
        return 'en'

    @staticmethod
    def _output_translate_result(result_info):
        print(result_info)

    #API for single word translation
    @staticmethod
    def single_translate(word, sentence="", proxies=None):
        sess = requests.session()
        req_dict = dict()
        js_dict = dict()
        srclang = BDTranslation._detect_lang(word)
        if proxies:
            req_dict['proxies'] = proxies
        result = BDTranslation._translate_request(sess, req_dict, js_dict, word, sentence, srclang)
        if result:
            BDTranslation._output_translate_result('{0} OK!'.format(word))
        else:
            BDTranslation._output_translate_result('{0} fail ...'.format(word))

    #API for multiple words translation
    def gevent_translate(self, filename, sentence="", proxies=None):
        if os.path.exists(filename):
            words = yaml.load(open(filename))
        sess = requests.session()
        req_dict = dict()
        js_dict = dict()
        srclang = BDTranslation._detect_lang(words[0])
        if proxies:
            req_dict['proxies'] = proxies
        params = {'sess':sess, 'req_dict':req_dict, 'js_dict':js_dict, 'sentence':sentence, 'srclang':srclang}
        #add words to queue
        self.words_tobe_t = deque([])
        line = 0
        for word in words:
            line += 1
            self.words_tobe_t.append((line,word))
            """
            result = BDTranslation._translate_request(sess, req_dict, js_dict, word, sentence, srclang)
            if result:
                BDTranslation._output_translate_result('Line {0}: {1} OK!'.format(line, word))
            else:
                BDTranslation._output_translate_result('Line {0}: {1} fail...'.format(line, word))
            """
        #start thread worker
        threads = []
        c_worker_size = 20
        for i in xrange(0,c_worker_size):
            threads.append( gevent.spawn(self.translate_worker, i+1, params) )
        gevent.joinall( threads )

    @staticmethod
    def make_anki_card(filename):
        if os.path.exists(filename):
            data = yaml.load(open(filename))
            word_obj = WordTranslateResult()
            flash_card = []
            line = 0
            for word in data:
                line += 1
                word_in_dict = word_obj.read_result_from_db(word)
                if word_in_dict:
                    #flash card info
                    result = word_obj.gen_flashcard_format()
                    flash_card.append((line,word,result))
            outfilename = '{0:%Y-%m-%d}_en_flashcard.txt'.format(datetime.datetime.today())
            with open(outfilename, 'w') as outf:
                for line, word, card in flash_card:
                    outf.write(card.encode('utf-8'))
                    outf.write('\n')
                print(line)

if __name__=="__main__":
    if len(argv)==2:
        script, filename = argv
        proxies = None
        translator = BDTranslation()
        translator.gevent_translate(filename, sentence="", proxies=proxies)
    elif len(argv)==3:
        script, filename, anki = argv
        proxies = None
        if 'anki' in anki:
            BDTranslation.make_anki_card(filename)
