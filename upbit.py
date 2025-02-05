import os
import base64
import re
import time
import json
import pyupbit
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# 1. Gmail API 인증 및 서비스 구축
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']  # 읽기 전용 권한 설정

# Upbit API 설정 (여기서 액세스 키와 비밀 키를 입력합니다)
access_key = 'd1JNKF2D7jiw5xhNWVMgSeI23Q6XsE2ZN1KySGlG'
secret_key = 'ndhAvQZQ2EB1xxYMoWCPRx6ceXAP4n9mxrdzvdKL'
upbit = pyupbit.Upbit(access_key, secret_key)

# 2. Gmail API 인증 함수
def authenticate_gmail():
    creds = None
    # 저장된 인증 토큰이 있으면 로드하고, 없으면 새로 인증
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # 만료된 토큰을 갱신
        else:
            # 새로 인증을 받기 위한 흐름
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_console()  # run_console()로 변경
        # 인증 후 토큰을 저장하여 이후 인증을 생략
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)  # Gmail API 서비스 객체 반환
    return service

# 3. TradingView에서 보낸 이메일을 가져오는 함수
def get_tradingview_email(service):
    # 'noreply@tradingview.com'에서 온 이메일만 가져옴
    results = service.users().messages().list(userId='me', q="from:noreply@tradingview.com").execute()
    messages = results.get('messages', [])
    
    if not messages:
        print('No new TradingView emails found.')  # 새로운 이메일이 없으면 출력
        return None
    
    # 가장 최근 이메일을 가져옴
    message = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
    # 이메일 본문을 디코딩하여 읽을 수 있게 변환
    msg_str = base64.urlsafe_b64decode(message['payload']['headers'][0]['value']).decode('utf-8')
    
    print("TradingView email found!")
    return msg_str  # 이메일 본문 반환

# 4. 이메일 본문에서 매매 신호를 추출하는 함수
def parse_email_content(msg_str):
    # 이메일 내용에서 Long/Short 신호와 종목명 및 가격을 정규식으로 추출
    match = re.search(r'([Long|Short])\s*.*\s*Symbol:\s*([A-Z]+)\s*Price:\s*([0-9,\.]+)', msg_str)
    if match:
        signal = match.group(1)  # Long/Short 신호
        symbol = match.group(2)  # 종목명
        price = float(match.group(3).replace(",", ""))  # 가격 (쉼표 제거 후 실수로 변환)
        return signal, symbol, price
    return None, None, None  # 매매 신호가 없으면 None 반환

# 5. 매수 또는 매도 주문을 실행하는 함수
def execute_trade(signal, symbol, price):
    if signal == "Long":
        # 1만원으로 매수 (수량 계산 없이 바로 금액을 전달)
        amount_to_invest = 10000  # 고정된 금액 1만원
        upbit.buy_market_order(symbol, amount_to_invest)
        print(f"Bought {symbol} for {amount_to_invest} KRW at {price}")
    elif signal == "Short":
        # 보유한 잔고를 이용해 시장가 매도
        balance = upbit.get_balance(symbol)  # 해당 종목 잔고
        if balance > 0:
            upbit.sell_market_order(symbol, balance * 0.9995)
            print(f"Sold {symbol} at {price}")

# 6. 봇을 24시간 운영하는 무한 루프
def run_bot():
    service = authenticate_gmail()  # Gmail 인증
    while True:
        try:
            print("Checking Gmail for new TradingView emails...")
            
            # Gmail에서 TradingView 이메일을 확인
            msg_str = get_tradingview_email(service)
            if msg_str:
                # 이메일에서 매매 신호 추출
                signal, symbol, price = parse_email_content(msg_str)
                if signal and symbol and price:
                    # 매매 신호가 유효하면 자동매매 실행
                    execute_trade(signal, symbol, price)
                else:
                    print("No valid trade signal in the email.")
            
            # 1분마다 이메일을 확인 (60초 후 반복)
            time.sleep(60)
        
        except Exception as e:
            # 오류가 발생하면 오류 메시지 출력하고 1분 후 다시 시도
            print(f"Error occurred: {e}")
            time.sleep(60)

# 7. 봇 실행
if __name__ == "__main__":
    run_bot()  # 자동매매 봇 시작
