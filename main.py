from fastapi import FastAPI, Query
import requests
import json
import time
import re

app = FastAPI()

# ========== হোম পেজ ==========
@app.get("/")
def root():
    return {"message": "API Running"}

# ========== শুধু রিটার্ন (পুরোনো) ==========
@app.get("/shopii")
def shopii(
    cc: str = Query(...),
    site: str = Query(...),
    proxy: str = Query(None)
):
    return {"cc": cc, "site": site, "proxy": proxy}

# ========== Shopify চেকার (আপডেটেড প্রক্সি সাপোর্ট) ==========
@app.get("/shopify")
def shopify_checker(
    site: str = Query(...),
    cc: str = Query(...),
    proxy: str = Query(...)
):
    start_time = time.time()
    
    # ===== কার্ড ডেটা পার্স =====
    card_parts = cc.split("|")
    if len(card_parts) != 4:
        return {"error": "Invalid card format. Use cc|mm|yy|cvv"}
    card_number, month, year, cvv = card_parts
    
    # ===== প্রক্সি পার্স (সব ফরম্যাট সাপোর্ট) =====
    proxy_config = parse_proxy(proxy)
    if "error" in proxy_config:
        return proxy_config
    
    # ===== Shopify কার্ট URL =====
    clean_site = site.replace("https://", "").replace("http://", "").strip("/")
    checkout_url = f"https://{clean_site}/cart.json"
    
    # ===== পেমেন্ট ডেটা =====
    payment_data = {
        "credit_card": {
            "number": card_number,
            "month": month,
            "year": year,
            "verification_value": cvv
        }
    }
    
    try:
        # ===== প্রক্সি সহ রিকোয়েস্ট =====
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
        
        elapsed_time = round(time.time() - start_time, 2)
        result = response.json()
        
        # ===== রেসপন্স প্রসেস =====
        if "error" in result:
            status = "CARD_DECLINED"
            approved = False
        elif "payment" in result and result["payment"].get("status") == "success":
            status = "CARD_APPROVED"
            approved = True
        else:
            status = "CARD_DECLINED"
            approved = False
        
        return {
            "Response": status,
            "CC": cc,
            "Price": "57.50",
            "Gate": "Shopify Payments",
            "Site": site,
            "Charged": str(approved),
            "Approved": str(approved),
            "Time": f"{elapsed_time}s",
            "Proxy": proxy_config["type"]
        }
        
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try a faster proxy."}
    except requests.exceptions.ProxyError as e:
        return {"error": f"Proxy Error: {str(e)}. Check your proxy credentials."}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# 🛠️ প্রক্সি পার্স ফাংশন (সব ফরম্যাট সাপোর্ট)
# ============================================================
def parse_proxy(proxy_str):
    """
    সাপোর্টেড ফরম্যাট:
    1. ip:port:user:pass
    2. user:pass@ip:port
    3. http://user:pass@ip:port
    4. ip:port (auth ছাড়া)
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
    
    # ফরম্যাট ৩: http://user:pass@ip:port
    if "://" in proxy_str:
        proxy_url = proxy_str
        return {
            "type": "Authenticated (URL)",
            "proxies": {
                "http": proxy_url,
                "https": proxy_url.replace("http://", "https://")
            }
        }
    
    # ফরম্যাট ৪: ip:port (auth ছাড়া)
    if ":" in proxy_str and len(proxy_str.split(":")) == 2:
        return {
            "type": "Unauthenticated",
            "proxies": {
                "http": f"http://{proxy_str}",
                "https": f"http://{proxy_str}"
            }
        }
    
    return {"error": "Invalid proxy format. Supported: ip:port:user:pass, user:pass@ip:port, ip:port"}
