# 1. get instagram user id
#	1.1. for first time users, ask for their instagram id, weibo account/password, store the password securely
#	1.2. retrieve instagram id from local storage
# 2. from user id, get user's "new" instagram profile
#	2.1. store user's latest post of instagram locally to diff later
#	2.2. schedule to check for new post every X minutes
# 3. prepare a list of new posts to be posted on Weibo
#	3.1.
# 4. use Weibo API / external libraries to post on Weibo
import os.path
import json
import getpass
import bs4
from base64 import b64encode, b64decode
from time import sleep
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup

INFO_FILE = os.path.join(Path.home(), '.instaweibo_info')
SECRET = os.path.join(Path.home(), '.secret')
INS_LATEST = os.path.join(Path.home(), '.insta_latest')
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIBO_REDIRECT = 'https://www.instagram.com/cuppad_wei/'
WEIBO_CODE = 'a6bd3eb88c31fe85f2a84468dde1d9c2'
WEIBO_TOKEN = '2.00KwDg_EKseELC3aee73cc2c0HAtYV'

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
	if (os.path.isfile(INFO_FILE)):
		return retrieve_user_info()
	else:
		return setup_user_info()

def setup_browser():
	options = Options()
	options.add_argument('--headless')
	options.add_argument('--disable-gpu')
	driver_path = os.path.join(ROOT_PATH, 'bin', 'chromedriver.exe')
	return webdriver.Chrome(executable_path = driver_path, chrome_options = options)

def set_current_ins_state(browser, ins_id):
	########## debug ###########
	# with open(INS_LATEST, 'w') as f:
	# 	f.write('/p/Btr4E0olMQX/')
	# return
	########## debug ###########
	browser.get('https://www.instagram.com/%s/' % ins_id)
	html = browser.page_source
	soup = BeautifulSoup(html, 'html.parser')
	article = soup.find('article')
	ins_latest = article.find('a').get('href')
	with open(INS_LATEST, 'w') as f:
		f.write(ins_latest)

def get_ins_diff_posts(browser, ins_id):
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
	posts = []
	for post_url in ins_posts:
		print(post_url)
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
		posts.append({'image_url': image, 'post': post})
	return posts

def main():
	user_info = load_user_info()
	browser = setup_browser()
	set_current_ins_state(browser, user_info['ins_id'])
	# in a loop
	ins_posts = get_ins_diff_posts(browser, user_info['ins_id'])
	weibo_posts = ins_to_weibo_posts(browser, user_info['ins_id'], ins_posts)


if (__name__ == '__main__'):
	main()
