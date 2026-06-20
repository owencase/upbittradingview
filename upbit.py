import imaplib
import email
from email.header import decode_header
import re
import time
import pyupbit

# 네이버 메일 로그인 정보
naver_email = "naver_id"  # 네이버 이메일
naver_password = "naver_password"  # 네이버 비밀번호

# Upbit API 키 설정
upbit_access_key = "access_key"  # Upbit Access Key
upbit_secret_key = "secret_key"  # Upbit Secret Key

# pyupbit 객체 생성
upbit = pyupbit.Upbit(upbit_access_key, upbit_secret_key)

# 고정 매수 가격 설정 (20,000 원)
fixed_buy_price = 20000

# 2. 네이버 메일에서 TradingView 이메일을 가져오는 함수
def get_tradingview_email():
    # IMAP 서버에 연결 (네이버 메일의 IMAP 서버)
    mail = imaplib.IMAP4_SSL("imap.naver.com")
    mail.login(naver_email, naver_password)
    
    # 'INBOX' 폴더 선택
    mail.select("inbox")
    
    # 읽지 않은 TradingView에서 보낸 이메일만 필터링
    status, messages = mail.search(None, '(UNSEEN FROM "noreply@tradingview.com")')
    
    if status != "OK" or not messages[0]:
        print("No new TradingView emails found.")
        return None, None  # 메시지가 없으면 None 반환
    
    # 최근 이메일을 가져옴 (마지막 이메일)
    try:
        latest_email_id = messages[0].split()[-1]
    except IndexError:
        print("Error: No emails found.")
        return None, None
    
    status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
    
    if status != "OK":
        print("Failed to fetch email.")
        return None, None
    
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            # 이메일 본문 추출
            msg_subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(msg_subject, bytes):
                msg_subject = msg_subject.decode(encoding or "utf-8")
            
            msg_from = msg.get("From")
            print(f"Subject: {msg_subject}")
            print(f"From: {msg_from}")
            
            # 이메일 본문이 텍스트일 경우
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    if "attachment" not in content_disposition:
                        if content_type == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            return body, latest_email_id
            else:
                body = msg.get_payload(decode=True).decode()
                return body, latest_email_id
            
    return None, None


# 3. 이메일 본문에서 매매 신호를 추출하는 함수
def parse_email_content(msg_str):
    # 이메일 내용에서 Long/Short 신호와 종목명 및 가격을 정규식으로 추출
    # '[Loxx]: Long' 또는 '[Loxx]: Short' 패턴을 추출
    match = re.search(r'\[Loxx\]:\s*(Long|Short)\s*Symbol:\s*([A-Z]+)KRW\s*Price:\s*([0-9,\.]+)', msg_str)
    if match:
        signal = match.group(1)  # Long/Short 신호
        symbol = match.group(2)  # 종목명
        price = float(match.group(3).replace(",", ""))  # 가격 (쉼표 제거 후 실수로 변환)
        return signal, symbol, price
    return None, None, None  # 매매 신호가 없으면 None 반환

# 4. 실제 매매 실행 함수 (pyupbit 사용)
def execute_trade(signal, symbol, price):
    # KRW를 빼고 'KRW-'를 붙여서 올바른 업비트 심볼을 만듦
    symbol = symbol.replace("KRW", "")  # KRW 제거
    symbol = f"KRW-{symbol}"  # KRW-을 붙여서 올바른 업비트 심볼 생성

    if signal == "Long":
        # 매수 (주문 가격은 고정값 40,000 원으로 매수)
        print(f"Placing a buy order for {symbol} at {fixed_buy_price} KRW")
        # 매수 (고정 금액으로 매수)
        upbit.buy_market_order(symbol, fixed_buy_price)
    elif signal == "Short":
        # 보유한 종목의 수량을 확인
        balance = upbit.get_balance(symbol)
        
        if balance > 0:
            # 보유한 수량만큼 매도 (시장가 매도)
            print(f"Placing a sell order for {symbol} at {price} KRW for {balance} units")
            upbit.sell_market_order(symbol, balance)
        else:
            print(f"No {symbol} available to sell.")

# 5. 봇을 24시간 운영하는 무한 루프
def run_bot():
    while True:
        try:
            print("Checking Naver email for new TradingView emails...")
            
            # 네이버 메일에서 TradingView 이메일을 확인
            msg_str, email_id = get_tradingview_email()
            if msg_str:
                # 이메일에서 매매 신호 추출
                signal, symbol, price = parse_email_content(msg_str)
                if signal and symbol and price:
                    # 매매 신호가 유효하면 자동매매 실행
                    print(f"Executing trade: {signal} {symbol} at {price}")
                    execute_trade(signal, symbol, price)  # 매매 실행
                    
                    # 이메일을 읽은 상태로 표시
                    mark_email_as_read(email_id)
                else:
                    print("No valid trade signal in the email.")
            
            # 1분마다 이메일을 확인 (60초 후 반복)
            time.sleep(10)
        
        except Exception as e:
            # 오류가 발생하면 오류 메시지 출력하고 1분 후 다시 시도
            print(f"Error occurred: {e}")
            time.sleep(20)

# 6. 이메일을 읽은 상태로 표시하는 함수
def mark_email_as_read(email_id):
    try:
        # IMAP 서버에 연결 (네이버 메일의 IMAP 서버)
        mail = imaplib.IMAP4_SSL("imap.naver.com")
        mail.login(naver_email, naver_password)
        
        # 'INBOX' 폴더 선택
        mail.select("inbox")
        
        # 이메일을 읽은 상태로 표시
        result = mail.store(email_id, '+FLAGS', '\\Seen')  # 읽음 상태로 표시
        if result[0] == 'OK':
            print(f"Marked email {email_id} as read.")
        else:
            print(f"Failed to mark email {email_id} as read. Result: {result}")
        
        # 세션 종료
        mail.close()
        mail.logout()
        
    except Exception as e:
        print(f"Error marking email {email_id} as read: {e}")


# 7. 봇 실행
if __name__ == "__main__":
    run_bot()  # 자동매매 봇 시작
