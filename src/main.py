# 1. get instagram user id
#	1.1. for first time users, ask for their instagram id, weibo account/password, store the password securely
#	1.2. retrieve instagram id from local storage
# 2. from user id, get user's "new" instagram profile
#	2.1. store user's latest post of instagram locally to diff later
#	2.2. schedule to check for new post every X minutes
# 3. prepare a list of new posts to be posted on Weibo
#	3.1.
# 4. use Weibo API / external libraries to post on Weibo
import os
import json
import getpass
import shutil
import requests
import time
from urllib import request
from base64 import b64encode, b64decode
from time import sleep
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

INFO_FILE = os.path.join(Path.home(), '.instaweibo_info')
SECRET = os.path.join(Path.home(), '.secret')
INS_LATEST = os.path.join(Path.home(), '.insta_latest')
WEIBO_TOKEN = os.path.join(Path.home(), '.weibo_credentials')
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIBO_KEY = '1995915790'
WEIBO_SECRET = '5ea4fa48c658b6e97bdfe1dde80bcd23'
WEIBO_REDIRECT = 'https://www.instagram.com/cuppad_wei/'
# WEIBO_CODE = 'a6bd3eb88c31fe85f2a84468dde1d9c2'
# WEIBO_TOKEN = '2.00KwDg_EKseELC3aee73cc2c0HAtYV'
#code = '4fbafd8801fa897750c0984db0ac248a'
#token = '2.00DEQs1EKseELC2a82a7b250Cld31E'

def get_key():
	if os.path.isfile(SECRET):
		with open(SECRET, 'rb') as f:
			key = f.read()
	else:
		key = get_random_bytes(16)
		with open(SECRET, 'wb') as f:
			f.write(key)
	return key

def encrypt(pt):
	b = pt.encode()
	key = get_key()
	cipher = AES.new(key, AES.MODE_CBC)
	ct_bytes = cipher.encrypt(pad(b, AES.block_size))
	iv = b64encode(cipher.iv).decode('utf-8')
	ct = b64encode(ct_bytes).decode('utf-8')
	return {'iv': iv, 'ct': ct}

def decrypt(b64iv, b64ct):
	key = get_key()
	iv = b64decode(b64iv)
	ct = b64decode(b64ct)
	cipher = AES.new(key, AES.MODE_CBC, iv)
	pt = unpad(cipher.decrypt(ct), AES.block_size)
	return pt

def setup_user_info():
	print('Please provide your account information below. Only encrypted password will be stored.')
	print('Instagram ID and password will be used to retrieve new posts to be posted on Sina Weibo.')
	ins_id = input('Instagram ID: ')
	print('Sina Weibo account and password will be used for posts.')
	weibo_id = input('Sina Weibo account: ')
	weibo_pass = getpass.getpass('Sina Weibo password: ')
	user_info = {'ins_id': ins_id, 'weibo_id': weibo_id, 'weibo_pass': weibo_pass}
	crypt = encrypt(json.dumps(user_info))
	with open(INFO_FILE, 'w+') as f:
		print(crypt['iv'], file = f)
		print(crypt['ct'], file = f)
	return user_info

def retrieve_user_info():
	with open(INFO_FILE, 'r') as f:
		crypt = f.readlines()
		iv = crypt[0]
		ct = crypt[1]
	user_info = json.loads(decrypt(iv, ct).decode('utf-8'))
	return user_info

def load_user_info():
	print('Loading user info...')
	if (os.path.isfile(INFO_FILE)):
		return retrieve_user_info()
	else:
		return setup_user_info()

def setup_browser():
	print('Setting up headless Chrome browser...')
	options = Options()
	options.add_argument('--headless')
	options.add_argument('--disable-gpu')
	driver_path = os.path.join(ROOT_PATH, 'bin', 'chromedriver.exe')
	return webdriver.Chrome(executable_path = driver_path, chrome_options = options)

def set_current_ins_state(browser, ins_id):
	print('recording current instagram post state...')
	########## debug ###########
	with open(INS_LATEST, 'w') as f:
		f.write('/p/Btr4E0olMQX/')
	return
	########## debug ###########
	browser.get('https://www.instagram.com/%s/' % ins_id)
	html = browser.page_source
	soup = BeautifulSoup(html, 'html.parser')
	article = soup.find('article')
	ins_latest = article.find('a').get('href')
	with open(INS_LATEST, 'w') as f:
		f.write(ins_latest)

def get_ins_diff_posts(browser, ins_id):
	print('retrieving new instagram posts...')
	with open(INS_LATEST, 'r') as f:
		latest = f.read()
	browser.get('https://www.instagram.com/%s/' % ins_id)
	for i in range(1):
		html = browser.page_source
		soup = BeautifulSoup(html, 'html.parser')
		article = soup.find('article')
		alist = article.find_all('a')
		links = []
		for a in alist:
			links.append(a.get('href'))
		if latest in links:
			idx = links.index(latest)
			links = links[:idx]
			break
		browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
		sleep(0.5)
	links.reverse()
	return links

def ins_to_weibo_posts(browser, ins_id, ins_posts):
	print('preparing weibo posts...')
	posts = []
	for post_url in ins_posts:
		browser.get('https://www.instagram.com%s' % post_url)
		html = browser.page_source
		soup = BeautifulSoup(html, 'html.parser')
		image = soup.find_all('img')[1]['src']
		comment = soup.select('.C4VMK')[0]
		user = comment.select('._6lAjh')[0].get_text()
		comment = comment.select('span')[0]
		for tag in comment.find_all('a'):
			tag.decompose()
		post = comment.get_text().strip() if user == ins_id else ''
		posts.append({'image_url': image, 'post': post, 'name': post_url[3:-1]})
	return posts

def get_weibo_access_token(browser, id, passwd):
	print('requesting weibo access token...')
	if os.path.isfile(WEIBO_TOKEN):
		with open(WEIBO_TOKEN, 'r') as f:
			cred = f.readlines()
			weibo_access_token = cred[0]
			token_expires_at = cred[1]
		if time.time() < float(token_expires_at):
			return weibo_access_token
	weibo_code_url = 'https://api.weibo.com/oauth2/authorize?client_id=%s&redirect_uri=%s&response_type=code' % (WEIBO_KEY, WEIBO_REDIRECT)
	browser.get(weibo_code_url)
	browser.find_element_by_id('userId').send_keys(id)
	sleep(1)
	browser.find_element_by_id('passwd').send_keys(passwd)
	sleep(3)
	browser.find_element_by_class_name('WB_btn_login').send_keys(Keys.ENTER)
	sleep(3)
	code = browser.current_url.split('code=')[-1]
	weibo_oauth_url = 'https://api.weibo.com/oauth2/access_token'
	payload = {
		'client_id': WEIBO_KEY,
		'client_secret': WEIBO_SECRET,
		'grant_type': 'authorization_code',
		'code': code,
		'redirect_uri': WEIBO_REDIRECT
	}
	r = requests.post(weibo_oauth_url, data=payload)
	response_json = json.loads(r.text)
	weibo_access_token = response_json['access_token']
	token_expires_at = time.time() + float(response_json['expires_in'])
	with open(WEIBO_TOKEN, 'w') as f:
		print(weibo_access_token, file=f)
		print(token_expires_at, file=f)
	return weibo_access_token

def post_weibo(weibo_posts, weibo_access_token):
	if len(weibo_posts) == 0:
		return
	print('uploading new weibo posts...')
	post = weibo_posts[0]
	weibo_api = 'https://upload.api.weibo.com/2/statuses/upload.json'
	with open(os.path.join(ROOT_PATH, 'github'), 'rb') as f:
		pic = f.read()
	status = ':o :P :D xD'
	payload = {
		'access_token': weibo_access_token,
		'status': status
	}
	files = {
		'pic': pic
	}
	r = requests.post(weibo_api, data=payload, files=files)
	print(r.text)


def main():
	user_info = load_user_info()
	browser = setup_browser()
	set_current_ins_state(browser, user_info['ins_id'])
	# in a loop
	ins_posts = get_ins_diff_posts(browser, user_info['ins_id'])
	weibo_posts = ins_to_weibo_posts(browser, user_info['ins_id'], ins_posts)
	weibo_access_token = get_weibo_access_token(browser, user_info['weibo_id'], user_info['weibo_pass'])
	post_weibo(weibo_posts, weibo_access_token)


if (__name__ == '__main__'):
	main()
