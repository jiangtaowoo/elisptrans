# -*- coding: utf-8 -*-
import transapi
import json
from flask import Flask, render_template
app = Flask(__name__)
trans_obj = transapi.BDTranslation()

@app.route('/vocabulary/<word>')
def process_trans(word):
    try:
        res = trans_obj.single_translate(word)
        res['result'] = 'success'
        return json.dumps(res)
    except:
        return json.dumps({'result':'fail'}) 

if __name__ == '__main__':
   app.run(host='0.0.0.0', port=8080)
