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
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from pathlib import Path

INFO_FILE = os.path.join(Path.home(), '.instaweibo_info')
SECRET = os.path.join(Path.home(), '.secret')
INS_URL = 'https://www.instagram.com/'

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

def setupUserInfo():
	print('Please provide your account information below.')
	print('Instagram ID will be used to retrieve new posts to be posted on Sina Weibo.')
	ins_id = input('Instagram ID: ')
	print('Sina Weibo account and password will be used for posts. Only encrypted password will be stored.')
	weibo_id = input('Sina Weibo account: ')
	weibo_pass = getpass.getpass('Sina Weibo password: ')
	user_info = {'ins_id': ins_id, 'weibo_id': weibo_id, 'weibo_pass': weibo_pass}
	crypt = encrypt(json.dumps(user_info))
	with open(INFO_FILE, 'w+') as f:
		print(crypt['iv'], file = f)
		print(crypt['ct'], file = f)
	return user_info

def retrieveUserInfo():
	with open(INFO_FILE, 'r') as f:
		crypt = f.readlines()
		iv = crypt[0]
		ct = crypt[1]
	user_info = json.loads(decrypt(iv, ct).decode('utf-8'))
	return user_info

def loadUserInfo():
	if (os.path.isfile(INFO_FILE)):
		return retrieveUserInfo()
	else:
		return setupUserInfo()

def setCurrentInsState(ins_id):
	pass

def main():
	print(INFO_FILE)
	user_info = loadUserInfo()
	setCurrentInsState(user_info['ins_id'])

if (__name__ == '__main__'):
	main()
