import os
import requests
from flask import Flask, render_template, redirect, request, session

app = Flask(__name__)
app.secret_key = os.urandom(24)

# api.py
# 이전 단계에서 입력한 코드
# :

client_id = "38b7fa84ad683f04ad8b685715ce3be9"      # 내 앱의 REST API 키로 변경 필수
client_secret = " WqY5WKi862qyKg5NzDLBu7dtEOyNHMuj "
domain = "http://localhost:3000"
redirect_uri = domain + "/redirect"
kauth_host = "https://kauth.kakao.com" # 액세스 토큰 요청을 보낼 카카오 인증 서버 주소
kapi_host = "https://kapi.kakao.com"   # 카카오 API 호출 서버 주소

@app.route("/")
def home():
    return render_template('index.html')

# api.py
# 이전 단계에서 입력한 코드
# :

# 카카오 인증 서버로 인가 코드 발급 요청
@app.route("/authorize")
def authorize():
    # 선택: 사용자에게 추가 동의를 요청하는 경우, scope 값으로 동의항목 ID를 전달
    # 친구 목록, 메시지 전송 기능의 경우, 추가 기능 신청 필요
    # (예: /authorize?scope=friends,talk_message)
    scope_param = ""
    if request.args.get("scope"):
        scope_param = "&scope=" + request.args.get("scope")

    # 카카오 인증 서버로 리다이렉트
    # 사용자 동의 후 리다이렉트 URI로 인가 코드가 전달
    return redirect(
        "{0}/oauth/authorize?response_type=code&client_id={1}&redirect_uri={2}{3}".format(
            kauth_host, client_id, redirect_uri, scope_param))


# 이전 단계에서 입력한 코드
#   :

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=4000)