# -*- coding: utf-8 -*-

___author___ = 'Zhanyang Li'
___version___ = '0.1'
___email___ = 'zhanyli46.dev@gmail.com'

import atexit
import getpass
import json
import os
import shutil
import sys
from base64 import b64encode, b64decode
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from urllib import request

INFO_FILE = os.path.join(Path.home(), '.instaweibo_info')
SECRET = os.path.join(Path.home(), '.secret')
INS_LATEST = os.path.join(Path.home(), '.insta_latest')
TEMP_PATH = os.path.join(Path.home(), 'temp')
UPDATE_INTERVAL = 1800

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
	window_size = '1024,768'
	user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.109 Safari/537.36'
	options.add_argument('--window-size=%s' % window_size)
	options.add_argument('--user-agent=%s' % user_agent)
	options.add_argument('--headless')
	options.add_argument('--disable-gpu')
	options.add_argument('--disable-web-security')
	driver_path = os.path.join(sys._MEIPASS, 'chromedriver.exe')
	browser = webdriver.Chrome(executable_path=driver_path, options=options)
	browser.execute_script('window.open("")')
	return browser

def set_current_ins_state(browser, ins_id):
	print('Recording current instagram post state...')
	browser.switch_to_window(browser.window_handles[0])
	browser.get('https://www.instagram.com/%s/' % ins_id)
	html = browser.page_source
	soup = BeautifulSoup(html, 'html.parser')
	article = soup.find('article')
	try:
		ins_latest = article.find('a').get('href')
	except:
		ins_latest = ''
	with open(INS_LATEST, 'w') as f:
		f.write(ins_latest)

def login_weibo(browser, weibo_id, weibo_pass):
	print('Logging in to weibo...')
	browser.switch_to_window(browser.window_handles[1])
	weibo_url = 'https://www.weibo.com/login.php'
	browser.get(weibo_url)
	browser.find_element_by_name('username').send_keys(weibo_id)
	browser.find_element_by_name('password').send_keys(weibo_pass)
	browser.find_element_by_class_name('W_btn_a').send_keys(Keys.ENTER)

def get_ins_diff_posts(browser, ins_id):
	print('Retrieving new instagram posts...')
	with open(INS_LATEST, 'r') as f:
		latest = f.read()
	browser.switch_to_window(browser.window_handles[0])
	browser.get('https://www.instagram.com/%s/' % ins_id)
	num_prev_posts = 0
	while True:
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
		if num_prev_posts == len(alist):
			break
		num_prev_posts = len(alist)
		browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
		sleep(0.5)
	links.reverse()
	return links

def ins_to_weibo_posts(browser, ins_id, ins_posts):
	print('Preparing weibo posts...')
	weibo_posts = []
	if not os.path.exists(TEMP_PATH):
		os.mkdir(TEMP_PATH)
	for post_url in ins_posts:
		browser.get('https://www.instagram.com%s' % post_url)
		html = browser.page_source
		soup = BeautifulSoup(html, 'html.parser')
		image_url = soup.find_all('img')[1]['src']
		comment = soup.select('.C4VMK')[0]
		user = comment.select('._6lAjh')[0].get_text()
		comment = comment.select('span')[0]
		for tag in comment.find_all('a'):
			tag.decompose()
		post = comment.get_text().strip() if user == ins_id else ''
		image_path = os.path.join(TEMP_PATH, post_url[3:-1]) + '.jpg'
		with open(image_path, 'wb') as f:
			f.write(request.urlopen(image_url).read())
		weibo_posts.append({'image_path': image_path, 'post': post, 'url': post_url})
	return weibo_posts

def post_weibo(browser, weibo_posts):
	if len(weibo_posts) == 0:
		print('Nothing to be post on weibo.')
		return
	browser.switch_to_window(browser.window_handles[1])
	WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.XPATH, '//textarea[@title="微博输入框"]')))
	print('Posting weibo...')
	i = 1
	ins_latest = ''
	for post in weibo_posts:
		print('Posting %d of %d...' % (i, len(weibo_posts)), end='')
		if post['post'] == '':
			post['post'] = u'分享图片'
		try:
			browser.find_element_by_xpath('//textarea[@title="微博输入框"]').send_keys(post['post'])
		except WebDriverException:
			browser.execute_script('document.getElementsByTagName("textarea")[0].value = "%s"' % post['post'])
		sleep(1)
		browser.find_element_by_xpath('//input[@name="pic1"]').send_keys(post['image_path'])
		sleep(3)
		browser.find_element_by_xpath('//a[@title="发布微博按钮"]').send_keys(Keys.ENTER)
		sleep(3)
		i += 1
		print(' succeeded.')
		last_post = post['url']
	print('Finished all weibo posts.')
	if last_post != '':
		with open(INS_LATEST, 'w') as f:
			f.write(last_post)

def hibernate(interval):
	print('Hibernating for %d seconds...' % interval)
	sleep(interval)

def cleanup(browser):
	print('Cleaning up...')
	if os.path.exists(TEMP_PATH):
		shutil.rmtree(TEMP_PATH)
	if os.path.exists(INS_LATEST):
		os.remove(INS_LATEST)
	browser.quit()

def main():
	user_info = load_user_info()
	browser = setup_browser()
	atexit.register(cleanup, browser)
	set_current_ins_state(browser, user_info['ins_id'])
	login_weibo(browser, user_info['weibo_id'], user_info['weibo_pass'])
	while True:
		ins_posts = get_ins_diff_posts(browser, user_info['ins_id'])
		weibo_posts = ins_to_weibo_posts(browser, user_info['ins_id'], ins_posts)
		post_weibo(browser, weibo_posts)
		hibernate(UPDATE_INTERVAL)

if (__name__ == '__main__'):
	main()
