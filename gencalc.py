# -*- coding: utf-8 -*-
import random

def set_weight(maxsum):
    if not (maxsum==10 or maxsum==20):
        return None
    #设置各个数字的概率
    rate = {0:[0,1,20], 2:[2,3,17,18,19], 5:[10,11,12,13,14,15,16], 10:[4,5,6,7,8,9]}
    rate_num = dict()
    rate_sum = 0
    for k, v in rate.items():
        for i in v:
            rate_num[i] = k
            rate_sum += k
    #计算各个数字的概率
    acc = 0
    weights = []
    for i in range(0,maxsum):
        acc += rate_num[i]
        weights.append(1.0*acc/rate_sum)
    return weights

def choose_num(weights):
    r = random.random()
    for i in range(0,len(weights)):
        if r<weights[i]:
            return i

# 20以内的加减法
## 1.随机生成 3*20 = 60 道 10以内的加减法题目# 10以内的加减法, plusratio为产生加法算式的几率, addinrate为进位的几率
def gen_exercise(minsum, maxsum, weights, plusrate=0.9, addinrate=0.8):
    a, b = 0, 0
    #先确定加法或是减法
    op = "+" if random.random()<plusrate else "-"
    addr = True if random.random()<addinrate else False
    #开始算式选择
    meet_require = False
    #随机生成第一个数a
    while not meet_require:
        a = choose_num(weights)
        b = choose_num(weights)
        if op=="+":
            if a+b>=minsum and a+b<=maxsum:
                if not addr:
                    break
                elif a<10 and b<10 and a+b>=10:
                    break
        else:
            if a<b:
                a, b = b, a
                break
    return "{0} {1} {2} = ".format(a,op,b), a, b, op

def genexpr(minsum, maxsum, weights, delimiter="\t"):
    history = []
    output = []
    for i in range(0,25):
        succ = 0
        while True:
            expr = gen_exercise(minsum, maxsum, weights)[0]
            #succ += 1
            #history.append(expr)
            if expr not in history:
                history.append(expr)
                succ += 1
            if succ>=4:
                break
        #print(history[-4]+delimiter+history[-3]+delimiter+history[-2]+delimiter+history[-1])
        output.append(delimiter.join(history[-4:]))
    return output

weights = set_weight(20)
#genexpr(7,20,weights,"|")
