#!/usr/bin/env python
#
# Stupid console app for the Twitter by Igor Bereznyak.
# Based on the 'oauth-python-twitter2' project. See http://code.google.com/p/oauth-python-twitter2/
#
#

from oauth import oauth
from oauthtwitter import OAuthApi
import select, sys, tty, os, re, webbrowser, pickle;
from time import mktime, strptime, localtime, strftime, sleep, time

if not __name__ == '__main__': exit(0)

# Read config file

config_fname = os.path.expanduser('~') + '/.my_stupid_twitter'

if os.path.exists(config_fname):
	f = open(config_fname, 'rb')
	config = pickle.load(f)
	f.close()
else:
	config = dict()
	config['consumer_key'] = raw_input('What is the consumer key? ')
	config['consumer_secret'] = raw_input('What is the consumer secret? ')

	# Request app's authorization
	twitter = OAuthApi(config['consumer_key'], config['consumer_secret'])

	# Get the temporary credentials for our next few calls
	temp_credentials = twitter.getRequestToken()

	# User pastes this into their browser to bring back a pin number
	print(twitter.getAuthorizationURL(temp_credentials))

	# Get the pin # from the user and get our permanent credentials
	oauth_verifier = raw_input('What is the PIN? ')
	access_tokens = twitter.getAccessToken(temp_credentials, oauth_verifier)
	config['oauth_token'] = access_tokens['oauth_token']
	config['oauth_token_secret'] = access_tokens['oauth_token_secret']

	f = open(config_fname, 'wb')
	pickle.dump(config, f)
	f.close()

# Connect to twittarr

twitter = OAuthApi(
	config['consumer_key'],
	config['consumer_secret'],
	config['oauth_token'],
	config['oauth_token_secret'])

# Main loop

showed = []
maxNameLength = 0
pollobj = select.poll()
pollobj.register(sys.stdin.fileno(), select.POLLIN)
tty.setraw(sys.stdin.fileno())
working = True
spinner = ['*_*', '0_0', 'o_o', '._.', 'x_x']
links = []
i = 0
link_sel = 0

while working:
	# Get timeline
	timeline = twitter.GetHomeTimeline()
	timeline.reverse()

	# Calculate numbers
	term_width = int(os.popen('stty size', 'r').read().split()[1]) -2
	maxNameLength = reduce(
		lambda acc, i : len(i['user']['screen_name']) if len(i['user']['screen_name']) > acc else acc,
		timeline, maxNameLength)
	text_prefix = reduce(lambda acc, i: acc + ' ', range(maxNameLength + 16), ' ')
	text_length = term_width - len(text_prefix)

	# Output lines
	for tweet in timeline:
		if tweet['id_str'] in showed: continue
		if tweet['user']['screen_name'] == 'aikawa_kozue': continue # TODO japanese characters breaks alignment
		created_at = mktime(strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y'))
		created_at += 60 * 60 * 4
		username = tweet['user']['screen_name']

		sys.stdout.write('\033[4m@%s\033[0m%s[\033[32m%s\033[0m] \033[35m' % (
			username,
			reduce(lambda acc, i: acc + ' ', range(maxNameLength - len(username)), ' '),
			strftime('%d %b \033[1m%H:%M', localtime(created_at))))
		
		tweet_text = tweet['text'].replace('\n', '') + ('[RT]' if tweet['retweeted'] else '')
		text = tweet_text
		while not text == '':
			sys.stdout.write(text[:text_length])
			text = text[text_length:]
			if not text == '': sys.stdout.write('\r\n' + text_prefix)

		sys.stdout.write('\033[0m \r\n')

		sys.stdout.flush()
		showed.append(tweet['id_str'])
		tweet_links = re.findall(r"(https?://[^\s]+)", tweet_text)
		links += map(lambda x: (username, x), tweet_links)

	# Wait and process keys input for around 2 minuts
	last_check = time()
	line_drawn = False
	if link_sel >= len(links): link_sel = 0
	while time() - last_check < 60 * 2:
		lnk = links[link_sel] if len(links) > 0 else ('', '')
		sys.stdout.write('\r[E(\033[36mx\033[0m)it%s%s] %s\033[K' % (
			(', (' + str(link_sel+1) + '/' + str(len(links)) + ')') if len(links) > 0 else '',
			(' \033[4m@' + lnk[0] + '\033[0m \033[1m' + lnk[1] + '\033[0m') if len(links) > 0 else '',
			spinner[i % len(spinner)]))
		sys.stdout.flush()
		i += 1
		ret = pollobj.poll(600)
		if len(ret) > 0:
			inp = sys.stdin.read(1)
			if inp in ['x', 'X']:
				working = False
				break
			elif inp == ' ' and not line_drawn:
				sys.stdout.write('\r\033[33m%s\033[0m\r\n' % reduce(lambda x, y: x + '-', range(term_width), ''))
				line_drawn = True
			elif inp == '\033':
				if sys.stdin.read(1) == '[':
					k = sys.stdin.read(1)
					if k == 'C':   link_sel += 1 # right
					elif k == 'D': link_sel -= 1 # left
			elif inp == '\r' and len(links) > 0:
				webbrowser.open(links[link_sel][1], new=2, autoraise=True)
				del links[link_sel]
				link_sel -= 1
			if link_sel >= len(links): link_sel = len(links)-1
			if link_sel < 0: link_sel = 0

	sys.stdout.write('\r\033[K')
	sys.stdout.flush()

os.system('reset')