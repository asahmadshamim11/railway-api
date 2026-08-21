from fastapi import FastAPI, Query, HTTPException
from typing import Optional
import requests
import json
import time
import urllib.parse
import os
import re

app = FastAPI(title="Shopify API Checker")

# ============================================================
# ১. হোম পেজ
# ============================================================
@app.get("/")
def root():
    return {
        "message": "API Running",
        "endpoints": {
            "/": "Home page",
            "/shopify": "Shopify card checker (main)",
            "/check-site": "Check if a site is alive",
            "/bulk-check": "Check multiple sites",
            "/check-proxy": "Check if a proxy is working"
        }
    }

# ============================================================
# ২. Shopify কার্ড চেকার (বটের check_card এর জন্য)
# ============================================================
@app.get("/shopify")
def shopify_checker(
    site: str = Query(..., description="Shopify store URL"),
    cc: str = Query(..., description="Card in format cc|mm|yy|cvv"),
    proxy: Optional[str] = Query(None, description="Proxy (optional)")
):
    start_time = time.time()
    
    # ===== কার্ড ডেটা পার্স =====
    card_parts = cc.split("|")
    if len(card_parts) != 4:
        return {
            "Response": "Invalid Format",
            "Gateway": "Unknown",
            "Price": "-",
            "error": "Invalid card format. Use cc|mm|yy|cvv"
        }
    card_number, month, year, cvv = card_parts
    
    # ===== প্রক্সি পার্স (যদি থাকে) =====
    proxy_config = None
    if proxy:
        proxy_parts = proxy.split(":")
        if len(proxy_parts) == 4:
            ip, port, user, password = proxy_parts
            proxy_url = f"http://{user}:{password}@{ip}:{port}"
            proxy_config = {
                "http": proxy_url,
                "https": proxy_url
            }
        else:
            return {
                "Response": "Proxy Error",
                "Gateway": "Unknown",
                "Price": "-",
                "error": "Invalid proxy format. Use ip:port:user:pass"
            }
    
    # ===== Shopify URL =====
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
        # ===== রিকোয়েস্ট =====
        if proxy_config:
            response = requests.post(
                checkout_url,
                json=payment_data,
                proxies=proxy_config,
                timeout=25,
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
                timeout=25,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        
        elapsed_time = round(time.time() - start_time, 2)
        
        # ===== রেসপন্স প্রসেস =====
        try:
            result = response.json()
        except:
            result = {"error": "Invalid JSON response"}
        
        # ===== স্ট্যাটাস চেক (বটের ফরম্যাটে) =====
        if "error" in result:
            status = "CARD_DECLINED"
            charged = "False"
            approved = "False"
            response_msg = str(result.get("error", "Unknown error"))
        elif "payment" in result and result["payment"].get("status") == "success":
            status = "CHARGED"
            charged = "True"
            approved = "True"
            response_msg = "Payment successful"
        elif "payment" in result and result["payment"].get("status") == "approved":
            status = "APPROVED"
            charged = "False"
            approved = "True"
            response_msg = "Payment approved"
        else:
            status = "CARD_DECLINED"
            charged = "False"
            approved = "False"
            response_msg = "Card declined"
        
        return {
            "Response": status,
            "Gateway": "Shopify Payments",
            "Price": "57.50",
            "Site": site,
            "Charged": charged,
            "Approved": approved,
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
    except requests.exceptions.ConnectionError as e:
        return {
            "Response": "Site Error",
            "Gateway": "Unknown",
            "Price": "-",
            "error": f"Connection Error: {str(e)}"
        }
    except Exception as e:
        return {
            "Response": "Site Error",
            "Gateway": "Unknown",
            "Price": "-",
            "error": str(e)
        }

# ============================================================
# ৩. সাইট চেকার (বটের test_site_with_price এর জন্য)
# ============================================================
@app.get("/check-site")
def check_site(site: str = Query(..., description="Site URL to check")):
    try:
        clean_site = site.replace("https://", "").replace("http://", "").strip("/")
        
        # HTTPS চেক
        try:
            response = requests.get(
                f"https://{clean_site}",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                allow_redirects=True
            )
            if response.status_code == 200:
                return {
                    "site": site,
                    "status": "ALIVE",
                    "code": response.status_code,
                    "protocol": "https"
                }
        except:
            pass
        
        # HTTP চেক
        try:
            response = requests.get(
                f"http://{clean_site}",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                allow_redirects=True
            )
            if response.status_code == 200:
                return {
                    "site": site,
                    "status": "ALIVE",
                    "code": response.status_code,
                    "protocol": "http"
                }
        except:
            pass
        
        return {"site": site, "status": "DEAD", "error": "Site unreachable"}
        
    except Exception as e:
        return {"site": site, "status": "DEAD", "error": str(e)}

# ============================================================
# ৪. বাল্ক সাইট চেক (বটের জন্য অতিরিক্ত)
# ============================================================
@app.get("/bulk-check")
def bulk_check(
    sites: str = Query(..., description="Comma separated site URLs"),
    proxy: Optional[str] = Query(None, description="Optional proxy")
):
    site_list = [s.strip() for s in sites.split(",") if s.strip()]
    results = []
    
    for site in site_list:
        result = check_site(site)
        results.append(result)
    
    return {
        "total": len(site_list),
        "alive": len([r for r in results if r.get("status") == "ALIVE"]),
        "dead": len([r for r in results if r.get("status") == "DEAD"]),
        "results": results
    }

# ============================================================
# ৫. প্রক্সি চেকার (বটের test_proxy এর জন্য)
# ============================================================
@app.get("/check-proxy")
def check_proxy(proxy: str = Query(..., description="Proxy to check")):
    try:
        proxy_parts = proxy.split(":")
        if len(proxy_parts) == 4:
            ip, port, user, password = proxy_parts
            proxy_url = f"http://{user}:{password}@{ip}:{port}"
        elif len(proxy_parts) == 2:
            ip, port = proxy_parts
            proxy_url = f"http://{ip}:{port}"
        else:
            return {"proxy": proxy, "status": "DEAD", "error": "Invalid proxy format. Use ip:port:user:pass"}
        
        response = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if response.status_code == 200:
            return {
                "proxy": proxy,
                "status": "ALIVE",
                "ip": response.json().get("origin", "Unknown")
            }
        else:
            return {"proxy": proxy, "status": "DEAD", "code": response.status_code}
            
    except requests.exceptions.Timeout:
        return {"proxy": proxy, "status": "DEAD", "error": "Timeout"}
    except requests.exceptions.ProxyError as e:
        return {"proxy": proxy, "status": "DEAD", "error": f"Proxy Error: {str(e)}"}
    except Exception as e:
        return {"proxy": proxy, "status": "DEAD", "error": str(e)}

# ============================================================
# ৬. BIN লুকআপ (বটের get_bin_info এর জন্য)
# ============================================================
@app.get("/bin")
def bin_lookup(bin: str = Query(..., description="6-digit BIN number")):
    if not bin.isdigit() or len(bin) < 6:
        return {"error": "Invalid BIN. Must be at least 6 digits"}
    
    try:
        response = requests.get(
            f"https://bins.antipublic.cc/bins/{bin[:6]}",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if response.status_code != 200:
            return {"error": "BIN not found"}
        
        data = response.json()
        return {
            "bin": bin[:6],
            "brand": data.get("brand", "-"),
            "type": data.get("type", "-"),
            "level": data.get("level", "-"),
            "bank": data.get("bank", "-"),
            "country": data.get("country_name", "-"),
            "flag": data.get("country_flag", ""),
            "prepaid": data.get("prepaid", False),
            "card_type": data.get("card_type", "-")
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ৭. IP লুকআপ (বটের ip_lookup এর জন্য)
# ============================================================
@app.get("/ip")
def ip_lookup(ip: str = Query(..., description="IP address to lookup")):
    # IP ফরম্যাট চেক
    ip_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    if not re.match(ip_pattern, ip):
        return {"error": "Invalid IP address"}
    
    try:
        response = requests.get(
            f"https://ipinfo.io/{ip}/json",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if response.status_code != 200:
            return {"error": "Failed to lookup IP"}
        
        data = response.json()
        
        # দেশের নাম
        country_name = data.get("country", "N/A")
        try:
            country_res = requests.get(
                f"https://restcountries.com/v3.1/alpha/{data.get('country', '')}",
                timeout=5
            )
            if country_res.status_code == 200:
                country_data = country_res.json()
                country_name = country_data[0].get("name", {}).get("common", data.get("country", "N/A"))
        except:
            pass
        
        return {
            "ip": data.get("ip", "N/A"),
            "hostname": data.get("hostname", "N/A"),
            "city": data.get("city", "N/A"),
            "region": data.get("region", "N/A"),
            "country": country_name,
            "country_code": data.get("country", "N/A"),
            "location": data.get("loc", "N/A"),
            "organization": data.get("org", "N/A"),
            "postal": data.get("postal", "N/A"),
            "timezone": data.get("timezone", "N/A")
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ৮. IBAN লুকআপ (বটের iban_lookup এর জন্য)
# ============================================================
@app.get("/iban")
def iban_lookup(iban: str = Query(..., description="IBAN to validate")):
    # IBAN ফরম্যাট চেক
    iban_clean = iban.replace(" ", "").upper()
    iban_pattern = r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{9,30}$'
    if not re.match(iban_pattern, iban_clean):
        return {"error": "Invalid IBAN format"}
    
    try:
        response = requests.get(
            f"https://openiban.com/validate/{iban_clean}?getBIC=true&validateBankCode=true",
            timeout=10
        )
        
        if response.status_code != 200:
            return {"error": "Failed to validate IBAN"}
        
        data = response.json()
        
        if not data.get("valid"):
            messages = data.get("messages", ["Invalid IBAN"])
            return {"error": ", ".join(messages)}
        
        bank_data = data.get("bankData", {})
        return {
            "iban": iban_clean,
            "valid": True,
            "messages": ", ".join(data.get("messages", ["Valid IBAN"])),
            "bank_name": bank_data.get("name", "N/A"),
            "bank_code": bank_data.get("bankCode", "N/A"),
            "bic": bank_data.get("bic", "N/A")
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ৯. স্ক্র্যাপ চেক (বটের detect_gateways এর জন্য)
# ============================================================
@app.get("/scg")
def site_scrape(site: str = Query(..., description="Site URL to scrape")):
    try:
        if not site.startswith("http"):
            site = f"https://{site}"
        
        response = requests.get(
            site,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "Accept": "text/html,application/xhtml+xml"
            }
        )
        
        html = response.text.lower()
        
        # গেটওয়ে ডিটেক্ট
        gateways = []
        if "js.stripe.com" in html or "stripe.com" in html:
            gateways.append("Stripe")
        if "paypal.com" in html or "paypalobjects.com" in html:
            gateways.append("PayPal")
        if "myshopify.com" in html or "cdn.shopify.com" in html:
            gateways.append("Shopify")
        if "braintreegateway.com" in html:
            gateways.append("Braintree")
        if "woocommerce" in html:
            gateways.append("WooCommerce")
        if "authorize.net" in html:
            gateways.append("Authorize.net")
        
        # CMS ডিটেক্ট
        cms = []
        if "wp-content" in html or "wp-json" in html:
            cms.append("WordPress")
        if "woocommerce" in html:
            cms.append("WooCommerce")
        if "myshopify.com" in html:
            cms.append("Shopify")
        if "magento" in html:
            cms.append("Magento")
        
        # ক্যাপচা ডিটেক্ট
        captcha = "None"
        if "recaptcha" in html or "g-recaptcha" in html:
            captcha = "reCAPTCHA"
        elif "hcaptcha" in html:
            captcha = "hCaptcha"
        
        # কার্ড ফর্ম চেক
        has_card_form = any([
            "cardnumber" in html or "ccnumber" in html,
            "cvv" in html or "cvc" in html,
            "expiry" in html or "expdate" in html
        ])
        
        return {
            "site": site,
            "status_code": response.status_code,
            "gateways": gateways if gateways else ["None"],
            "cms": cms if cms else ["Unknown"],
            "captcha": captcha,
            "has_card_form": "Yes" if has_card_form else "No",
            "server": response.headers.get("Server", "N/A")
        }
    except Exception as e:
        return {"site": site, "error": str(e)}

# ============================================================
# ১০. হেলথ চেক (Railway-এর জন্য)
# ============================================================
@app.get("/health")
def health():
    return {"status": "ok"}

# ============================================================
# ১১. মেইন ফাংশন
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
