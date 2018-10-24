import json
import functools
import requests
from django.conf import settings
from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
from app01 import models
# 沙箱环境地址：https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login

def index(request):
    '''
    测试是否拿到了这个wx_id
    :param request:
    :return:
    '''
    obj = models.UserInfo.objects.get(id=1)
    return render(request,'index.html',{'obj':obj})


def auth(func):
    '''
    登录认证的装饰器函数【其实可以写成一个中间件】
    :param func:
    :return:
    '''
    @functools.wraps(func)
    def inner(request, *args, **kwargs):
        user_info = request.session.get('user_info')
        if not user_info:
            return redirect('/login/')
        return func(request, *args, **kwargs)
    return inner


def login(request):
    """
    用户登录
    :param request: 
    :return: 
    """
    # models.UserInfo.objects.create(username='jesi',password=123)

    if request.method == "POST":
        user = request.POST.get('user')
        pwd = request.POST.get('pwd')
        obj = models.UserInfo.objects.filter(username=user, password=pwd).first()
        if obj:
            # 登录成功，将这三个值放到session中
            request.session['user_info'] = {'id': obj.id, 'name': obj.username, 'uid': obj.uid}
            return redirect('/bind/')
    else:
        return render(request, 'login.html')


@auth
def bind(request):
    """
    用户登录后，关注公众号，并绑定个人微信（用于以后消息推送）
    :param request: 
    :return: 
    """
    return render(request, 'bind.html')


@auth
def bind_qcode(request):
    """
    生成二维码
    :param request: 
    :return: 
    """
    ret = {'code': 1000}
    try:
        access_url = "https://open.weixin.qq.com/connect/oauth2/authorize?appid={appid}&redirect_uri={redirect_uri}&response_type=code&scope=snsapi_userinfo&state={state}#wechat_redirect"
        access_url = access_url.format(
            appid=settings.WECHAT_CONFIG["app_id"], # 'wx961b82840037d073',
            redirect_uri=settings.WECHAT_CONFIG["redirect_uri"], # 'http://47.99.191.149/callback/',
            state=request.session['user_info']['uid'] # 为当前用户生成MD5值
        )
        ret['data'] = access_url
    except Exception as e:
        ret['code'] = 1001
        ret['msg'] = str(e)

    return JsonResponse(ret)


def callback(request):
    """
    用户在手机微信上扫码后，微信自动调用该方法。
    用于获取扫码用户的唯一ID，以后用于给他推送消息。
    :param request: 
    :return: 
    """
    code = request.GET.get("code")

    # 用户md5值
    state = request.GET.get("state")

    # 获取该用户openId(用户唯一，用于给用户发送消息)
    res = requests.get(
        url="https://api.weixin.qq.com/sns/oauth2/access_token",
        params={
            "appid": 'wx961b82840037d073',
            "secret": 'c3f919fab6cd528a6ed727c911e1c599',
            "code": code,
            "grant_type": 'authorization_code',
        }
    ).json()
    # 获取的到openid表示用户授权成功
    openid = res.get("openid")
    if openid:
        #将这个用户的wx_id和他的用户这条数据进行一个绑定
        models.UserInfo.objects.filter(uid=state).update(wx_id=openid)
        response = "<h1>授权成功 %s </h1>" % openid
    else:
        response = "<h1>用户扫码之后，手机上的提示</h1>"
    return HttpResponse(response)


def sendmsg(request):
    def get_access_token():
        """
        获取微信全局接口的凭证(默认有效期俩个小时)
        如果不每天请求次数过多, 通过设置缓存即可
        """
        result = requests.get(
            url="https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.WECHAT_CONFIG['app_id'],
                "secret": settings.WECHAT_CONFIG['appsecret'],
            }
        ).json()
        if result.get("access_token"):
            access_token = result.get('access_token')
        else:
            access_token = None
        return access_token

    access_token = get_access_token()
    print(access_token)

    openid = models.UserInfo.objects.get(id=1).wx_id

    def send_custom_msg():
        body = {
            "touser": openid,
            "msgtype": "text",
            "text": {
                "content": '欢迎Python鬼才！'
            }
        }
        response = requests.post(
            url="https://api.weixin.qq.com/cgi-bin/message/custom/send",
            params={
                'access_token': access_token
            },
            data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8')
        )
        # 这里可根据回执code进行判定是否发送成功(也可以根据code根据错误信息)
        result = response.json()
        return result

    def send_template_msg():
        """
        发送模版消息
        """
        res = requests.post(
            url="https://api.weixin.qq.com/cgi-bin/message/template/send",
            params={
                'access_token': access_token
            },
            json={
                "touser": openid,
                "template_id": 'w7OBa8MhE6sNxgNSnooTqB93kgvMbA8JEhwN85vjUdY',
                "data": {
                    "first": {
                        "value": "杨康",
                        "color": "#173177"
                    },
                    "keyword": {
                        "value": "Python鬼才",
                        "color": "#173177"
                    },
                }
            }
        )
        result = res.json()
        return result

    result = send_template_msg()

    if result.get('errcode') == 0:
        return HttpResponse('发送成功')
    return HttpResponse('发送失败')
