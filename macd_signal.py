import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

# --- MACD Berechnung ---
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_macd(prices, fast=19, slow=39, signal=9):
    macd = ema(prices, fast) - ema(prices, slow)
    signal_line = ema(macd, signal)
    hist = macd - signal_line
    return macd, signal_line, hist

# --- DAX Daten holen ---
def get_dax_data():
    dax = yf.download("^GDAXI", period="6mo", interval="1d", progress=False)
    return dax["Close"].dropna()

# --- Signal ermitteln ---
def get_signal(prices):
    macd, signal_line, hist = calc_macd(prices)
    
    today_macd = macd.iloc[-1]
    today_sig  = signal_line.iloc[-1]
    prev_macd  = macd.iloc[-2]
    prev_sig   = signal_line.iloc[-2]
    
    cross_below = prev_macd >= prev_sig and today_macd < today_sig  # Bearish → Hedge
    cross_above = prev_macd <= prev_sig and today_macd > today_sig  # Bullish → Frei
    
    if cross_below:
        return "HEDGE", today_macd, today_sig, prices.iloc[-1]
    elif cross_above:
        return "FREI", today_macd, today_sig, prices.iloc[-1]
    else:
        # Kein Crossover - trotzdem Status melden
        status = "ABSICHERN (laufend)" if today_macd < today_sig else "LONG (laufend)"
        return status, today_macd, today_sig, prices.iloc[-1]

# --- E-Mail senden ---
def send_email(signal, macd_val, sig_val, dax_level):
    sender    = os.environ["EMAIL_FROM"]
    recipient = os.environ["EMAIL_TO"]
    password  = os.environ["EMAIL_PASSWORD"]
    
    is_action = signal in ["HEDGE", "FREI"]
    subject_prefix = "⚠️ SIGNAL" if is_action else "📊 STATUS"
    
    if signal == "HEDGE":
        emoji = "🔴"
        action_text = "MACD kreuzt Signal von oben — ABSICHERN"
        color = "#E24B4A"
    elif signal == "FREI":
        emoji = "🟢"
        action_text = "MACD kreuzt Signal von unten — LONG FREIGEBEN"
        color = "#3B6D11"
    elif "ABSICHERN" in signal:
        emoji = "🟡"
        action_text = "Hedge aktiv — kein neues Signal heute"
        color = "#BA7517"
    else:
        emoji = "🔵"
        action_text = "Long aktiv — kein neues Signal heute"
        color = "#185FA5"
    
    date_str = datetime.now().strftime("%d.%m.%Y")
    
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <div style="background:{color};color:white;padding:16px 20px;border-radius:8px 8px 0 0;">
        <div style="font-size:22px;font-weight:bold;">{emoji} DAX MACD Signal</div>
        <div style="font-size:13px;opacity:0.85;">{date_str} · 19/39/9</div>
      </div>
      <div style="border:1px solid #e0e0e0;border-top:none;padding:20px;border-radius:0 0 8px 8px;">
        <div style="font-size:16px;font-weight:600;margin-bottom:16px;">{action_text}</div>
        <table style="width:100%;font-size:14px;border-collapse:collapse;">
          <tr style="border-bottom:1px solid #f0f0f0;">
            <td style="padding:8px 0;color:#666;">DAX-Stand</td>
            <td style="padding:8px 0;text-align:right;font-weight:600;">{dax_level:,.0f}</td>
          </tr>
          <tr style="border-bottom:1px solid #f0f0f0;">
            <td style="padding:8px 0;color:#666;">MACD</td>
            <td style="padding:8px 0;text-align:right;">{macd_val:.1f}</td>
          </tr>
          <tr>
            <td style="padding:8px 0;color:#666;">Signal-Linie</td>
            <td style="padding:8px 0;text-align:right;">{sig_val:.1f}</td>
          </tr>
        </table>
        <div style="margin-top:16px;padding:10px;background:#f8f8f8;border-radius:4px;font-size:12px;color:#888;">
          MACD {"unter" if macd_val < sig_val else "über"} Signal-Linie · 
          Differenz: {macd_val - sig_val:.1f}
        </div>
      </div>
    </div>
    """
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject_prefix}: DAX {emoji} {signal} — {date_str}"
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html"))
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    
    print(f"Signal '{signal}' gesendet an {recipient}")

# --- Hauptprogramm ---
if __name__ == "__main__":
    print(f"DAX MACD Signal-Check — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    prices = get_dax_data()
    signal, macd_val, sig_val, dax_level = get_signal(prices)
    print(f"Signal: {signal} | DAX: {dax_level:.0f} | MACD: {macd_val:.1f} | Signal-Linie: {sig_val:.1f}")
    send_email(signal, macd_val, sig_val, dax_level)
