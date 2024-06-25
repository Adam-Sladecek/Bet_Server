def getCommonDriver(showBrowser):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    import subprocess
    service = Service('chromedriver.exe',log_output=subprocess.DEVNULL)
    service.creation_flags = subprocess.CREATE_NO_WINDOW
    options = Options()
    options.add_argument('--no-sandbox')
    if not showBrowser: 
        options.add_argument("--headless=new")
        options.add_argument('--disable-gpu')
        options.add_argument('--log-level=3')   
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-translate")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1920,1080")
    
    options.add_argument('--show-capture=no')   
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation']) 
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--mute-audio')
    options.add_argument('--remote-debugging-port=0') 
    options.add_argument("--disable-notifications")
    options.add_argument("--output=/dev/null")
    options.add_argument("--disable-in-process-stack-traces")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-crash-reporter")
    driver = webdriver.Chrome(service= service, options = options)
    return driver