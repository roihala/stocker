import random
from concurrent.futures.thread import ThreadPoolExecutor

import requests
from requests import ReadTimeout, ConnectTimeout
from fake_useragent import UserAgent
from requests.auth import HTTPProxyAuth
from retry import retry

proxy = "http://zproxy.lum-superproxy.io:22225"
ua = UserAgent(use_cache_server=True)

ips_local = [
    {'ip': "158.46.169.208"},
    {'ip': "158.46.169.252"},
    {'ip': "158.46.169.76"},
    {'ip': "158.46.171.23"},
    {'ip': "158.46.171.41"},
    {'ip': "158.46.172.120"},
    {'ip': "158.46.172.217"},
    {'ip': "158.46.172.230"},
    {'ip': "158.46.172.253"},
    {'ip': "158.46.172.55"},
    {'ip': "158.46.172.98"},
    {'ip': "158.46.173.104"},
    {'ip': "158.46.173.109"},
    {'ip': "158.46.173.140"},
    {'ip': "158.46.173.219"},
    {'ip': "158.46.173.253"},
    {'ip': "181.214.179.208"},
    {'ip': "181.214.179.41"},
    {'ip': "181.214.180.215"},
    {'ip': "181.214.185.194"},
    {'ip': "181.214.185.198"},
    {'ip': "181.214.185.199"},
    {'ip': "181.214.185.202"},
    {'ip': "181.214.185.213"},
    {'ip': "181.214.185.214"},
    {'ip': "181.214.185.215"},
    {'ip': "181.214.185.217"},
    {'ip': "181.214.185.220"},
    {'ip': "181.214.185.39"},
    {'ip': "181.214.185.43"},
    {'ip': "181.214.185.57"},
    {'ip': "181.214.185.61"},
    {'ip': "181.214.187.38"},
    {'ip': "181.214.189.192"},
    {'ip': "181.214.189.41"},
    {'ip': "181.214.189.60"},
    {'ip': "181.214.190.219"}
]


@retry(tries=12, delay=1)
def get_ips():
    try:
        res = requests.get("https://brightdata.com/api/zone/ips?zone=data_center",
                           headers={"Authorization": "Bearer 9a8bc5df8b0e14bc21f1ca755f37714d"}, timeout=60)
        print("Success!")

    except Exception as e:
        print(e)
    global ips
    result = res.json()['ips']
    return result


def get_ips_local():
    return ips_local


ips = get_ips_local()


def get_proxy_auth():
    username = 'lum-customer-c_050c0806-zone-data_center'
    password = '/ykw+71y9e~o'
    ip = get_random_ip()
    auth = HTTPProxyAuth("%s-ip-%s" % (username, ip), password)
    return auth


def get_random_ip():
    ip = random.choice(ips)
    return ip['ip']


def send_http(url):
    session = requests.Session()
    session.auth = get_proxy_auth()
    session.trust_env = False
    session.proxies = {"http": proxy, "https": proxy}

    response = session.get(url, timeout=5)
    print(response.json())


def send_https(url):
    import urllib.request
    import random
    username = 'lum-customer-c_050c0806-zone-data_center'
    password = '/ykw+71y9e~o'
    port = 22225
    session_id = random.random()
    super_proxy_url = ('http://%s-session-%s:%s@zproxy.lum-superproxy.io:%d' %
                       (username, session_id, password, port))
    proxy_handler = urllib.request.ProxyHandler({
        'http': super_proxy_url,
        'https': super_proxy_url,
    })
    proxy_handler = urllib.request.ProxyHandler(
        {'http': 'http://lum-customer-c_050c0806-zone-residential:2v??7_3*1!p$@zproxy.lum-superproxy.io:22225',
         'https': 'http://lum-customer-c_050c0806-zone-residential:2v??7_3*1!p$@zproxy.lum-superproxy.io:22225'})
    opener = urllib.request.build_opener(proxy_handler)
    browser = ua.chrome
    opener.addheaders = [('user-agent',
                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"),
                         ("accept",
                          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"),
                         ("accept-language", "en-US,en;q=0.9"),
                         ("accept-encoding", "gzip, deflate, br"),
                         ("cache-control", "max-age=0"),
                         ("referer", "https://esos.nv.gov/EntitySearch/BusinessFilingHistory?businessid=615150"),
                         # ("Content-Type", "text/plain; charset=utf-8"),
                         # ("Origin", "https://esos.nv.gov"),
                         ("sec-fetch-dest", "document"),
                         ("sec-fetch-mode", "navigate"),
                         ("sec-fetch-site", "same-origin"),
                         ("sec-ch-ua", '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"'),
                         ("upgrade-insecure-requests", "1"),
                         ("cookie",
                          "visid_incap_2373390=zEH1iarZR42iJ5Xa7o/dGtMDAGEAAAAAQUIPAAAAAACPfuCA3fOKVRcVTBi/aqGH; incap_ses_1051_2373390=jVS3Nyywnga57n344ueVDtMDAGEAAAAAb4pv2RYTP4BWa6WQSGwkYg==; ESSCookieEncypt=!1mOc+7qYnXBJj61ujBD7DxpJgoX6j1uo+z7SdngWHuwf3ulg85D9cEPfXLGmVDbG6JKW1VOzFCcZJXMQWL4CWCfxwLwquv1JqBRdemLZbXVlzQozTuq9sHn8uMnxT8O/0MsfOo0WPAE95nxehPCKmrXTr1+SLs0=; nlbi_2373390=LNsJRvF6NQCJpiKwM+c3awAAAACTz1wlX4Ar4okyb/hT0Vwb; nlbi_2373390_2147483646=G8tKBsnPsXdwV9WkM+c3awAAAABunLCIjxNeJCWLysFQEmnc; reese84=3:ClFhriLL4oxHmZw1d6r2Uw==:NL7gNN4CZ2Qhce9+yu/ApFCOIK0+gYqLOYDEFcib31KEknznXGo2rcni/24eC4oSxF4Ya9O6QxPtyfLErc4fZykzVFpzJFnfiKQcCGFoYZyX/bFJif/uQqy/36RWSiVH6a2iRsg4YdoKU1qnhWLhMlVW8fbg7OmjsQJCw9Kv535fHyRIXiGOt0EEg8C0hVIEwzf7ydEXcOTDjLVgZpukazy0XJFdBZ5qgETnma9xwJfgbxMAQmd+Ye0cktH2e1uU+MvvU5u/B8Zltrw6ITVJuTMkFyvF6u8aqsdjROuKnt9a2YipBcSKKm/7O4b//ouuSklJUDituBRcLhEPK3tBvyZ2V0N+KzKkFwdZ7QvLJbV3h5ZKO3NdcxvDgto1Y/nxaJJxcFUyKH1S+HHeUbDE9iUJH4/Vn1SOjFmX7A1k5sY=:IHWN9F84yDiWAFAeyccSgJPZyof0rnLy4W0OsywmKOA=")]

    # ("TE", "trailers")]
    # ("Cookie", "visid_incap_2373390=kUWUfqLEQWGiMK3xY57xSKBk9GAAAAAAQUIPAAAAAAAJltrICXBQUxhs9JZqAZ49; incap_ses_1051_2373390=tgFFKraQv1NuEm/44ueVDsTj/2AAAAAAQnI9RvLO45jBI4AMOuoFQA==; nlbi_2373390_2147483646=VxHDKBxGBDRpe7eCM+c3awAAAACQubZOU1lA4vWY7qqrMrQ1; ESSCookieEncypt=!FEd74KCBFtbiFGFujBD7DxpJgoX6j7eBhBgolL31Evm3/bkSU4CWR33KLP0E/DgLyz3ud1ffxqx6G//QhK1BGv9Mim2hklbHNRPhzXRz/mvPJNDPThJH8dn9iSzfGBeSA6CsSKQT/9GBGYmwQ6knj4fk7hc3BBE=; nlbi_2373390=Je6ySr5Po0bSoEwfM+c3awAAAADV9Zo8NqcvFW4JtIZyqhhr; reese84=3:mX7+LvJ8Elve47UOisx/Pw==:U5iJc9QJYEZQU9LdKxB78XqV7O4WHrohUYwKz2+MjMnFT5qkTf85vQUdjPdkEfzQb/g9vodwL3nGMYr93uCdTUOwtVEgNH+zo7wU6+eTIser42Kc48OVu+qq26m0yhqX1vpS0i3j2MdHeDB/PYwdLB4xcDBP7M6ERCjDL6aj4cej6baMlDUY34IYFYeePLFbu4eTJTYF8xChZBMN2bYkzG7YMRa6C6d+54GWewyc6+3uXoYftKmxkUpKRBhioUA7cEv2EXXVZUzFHDgr0VZRK4j99TODuA59WRWr2Sz0v0nVPX4tYfkbHv6w9e1SfOAHC0ea4sQ3aMRkdA5SZAxr4cRFS9TSlJemYsRYZRBRil5yTFVr0OkZ4sqj7Fejlbj1HQlugR0Uyt9iz31lpSUznAptN4XqtcLqtJx+YiUz5IM=:jsWvgAoLd1dWFvkXeshbsoQjDlk4Zl62RUOwYSSevEc=")]
    print('Performing request')
    response = opener.open(url)
    print(response)
    content = response.read()
    print(content)


if __name__ == "__main__":
    # test()
    import datetime

    # otc_url = "http://backend.otcmarkets.com/otcapi/company/profile/full/INNTW?symbol=INNTW"
    esos_url = "https://esos.nv.gov/EntitySearch/BusinessFilingHistory?businessid=615150"

    for i in range(30):
        before = datetime.datetime.now()
        send_https(esos_url)
        after = datetime.datetime.now()
        print((after - before).total_seconds())
