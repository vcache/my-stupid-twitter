#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Stupid console app for the Twitter by Igor Bereznyak.
# Based on the 'oauth-python-twitter2' project. See http://code.google.com/p/oauth-python-twitter2/
#
# TODO japanese characters breaks alignment

from oauth import oauth
from oauthtwitter import OAuthApi
import select, sys, tty, os, re, webbrowser, pickle, curses, locale, errno;
from time import mktime, strptime, localtime, strftime, sleep, time

if not __name__ == '__main__': exit(0)

config_fname = os.path.expanduser('~') + '/.my_stupid_twitter'
tweets_fname = os.path.expanduser('~') + '/.my_stupid_twitts'

# Read config file

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

# Load old tweets

if os.path.exists(tweets_fname):
	f = open(tweets_fname, 'rb')
	tweets = pickle.load(f)
	f.close()
else:
	tweets = []

# Main loop

def addTweetsToLines(tweets, lines, max_username):
	for tweet in tweets:
		created_at = tweet['created_at'].split(' ') #Mon Sep 16 18:20:50 +0000 2013
		time_at = created_at[3].split(':')
		username = tweet['user']['screen_name']
		tweet_text = tweet['text'].replace('\n', '') + ' // ' + tweet['user']['name'] + ' //'

		line_blocks = [
			['@' + username, curses.A_UNDERLINE | curses.color_pair(1)],
			[reduce(lambda acc, i: acc + ' ', range(max_username - len(username)), ' '), curses.color_pair(2)],
			['[', curses.color_pair(2)],
			[created_at[2]+' '+created_at[1]+' ', curses.color_pair(4)],
			[time_at[0]+':'+time_at[1], curses.color_pair(4) | curses.A_BOLD],
			[']', curses.color_pair(2)],
			[' ', curses.color_pair(2)],
			[tweet_text, curses.color_pair(3)]]
		line_blocks.reverse()
		lines.append(line_blocks)

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

maxNameLength = reduce(
	lambda acc, i : len(i['user']['screen_name']) if len(i['user']['screen_name']) > acc else acc,
	tweets, 0)
pollobj = select.poll()
pollobj.register(sys.stdin.fileno(), select.POLLIN)
working = True

stdscr = curses.initscr()
curses.start_color()
curses.use_default_colors()
curses.noecho()
curses.cbreak()
curses.curs_set(0)
stdscr.keypad(1)
stdscr.nodelay(1)
curses.init_pair(1, curses.COLOR_BLACK, -1) # @username
curses.init_pair(2, -1, -1) # whitespace
curses.init_pair(3, curses.COLOR_MAGENTA, -1) # whitespace
curses.init_pair(4, curses.COLOR_GREEN, -1) # whitespace

last_check = 0
lines = []
addTweetsToLines(tweets, lines, maxNameLength)
tweet_ids = map(lambda x : x['id_str'], tweets)

cursor = len(lines) - 1 if lines else 0

while working:
	# Load new tweets
	new_tweets = []
	if time() - last_check >= 60 * 3:
		timeline = twitter.GetHomeTimeline()
		timeline.reverse()

		for t in timeline:
			if not t['id_str'] in tweet_ids:
				new_tweets.append(t)
				tweets.append(t)
				tweet_ids.append(t['id_str'])
		last_check = time()

	# Build lines
	if len(new_tweets) > 0:
		maxNameLength = reduce(
			lambda acc, i : len(i['user']['screen_name']) if len(i['user']['screen_name']) > acc else acc,
			new_tweets, maxNameLength)
		addTweetsToLines(new_tweets, lines, maxNameLength)

	# Output lines
	maxyx = stdscr.getmaxyx()
	tweets_in_screen = maxyx[0] - 1
	first_tweet = int(round(cursor / tweets_in_screen) * tweets_in_screen)
	stdscr.erase()
	for i in range(tweets_in_screen):
		tweet_index = first_tweet + i
		if tweet_index >= len(lines): continue
		sel_attr = curses.A_BOLD if i == cursor - first_tweet else 0

		for blk in lines[tweet_index]:
			stdscr.insstr(i, 0, blk[0].encode(code), blk[1] | sel_attr)

		if i == cursor - first_tweet:
			stdscr.insstr(i, 0, "> ".encode(code), curses.A_BOLD)
		else:
			stdscr.insstr(i, 0, "  ".encode(code), 0)
	
	#re.findall(r"(https?://[^\s]+)", lines[cursor][0][0])
	tweet_urls = tweets[cursor]['entities']['urls'] if 'urls' in tweets[cursor]['entities'] else []
	tweet_media = tweets[cursor]['entities']['media'] if 'media' in tweets[cursor]['entities'] else [] # 'media_url'
	tweet_links = tweet_urls + tweet_media
	if tweet_links:
		status_line = reduce(lambda x, y: x + ' | ' + y['expanded_url'], tweet_links, '')
		stdscr.insstr(maxyx[0]-1, 0, status_line.encode(code), curses.A_REVERSE)

	status_line = '%d/%d' % (cursor + 1, len(lines))
	stdscr.insstr(maxyx[0]-1, 0, status_line.encode(code), curses.A_REVERSE | curses.A_BOLD)

	stdscr.refresh()

	# Wait and process keys input for around 2 minuts
	try:
		ret = pollobj.poll(1000)
	except: #IOError, e:
		#if not e.errno == errno.EINTR: working = False
		continue

	if len(ret) > 0:
		c = stdscr.getch()
		if c in [ord('x'), ord('X')]:
			working = False
		elif c == curses.KEY_DOWN:
			cursor += 1
		elif c == curses.KEY_UP:
			cursor -= 1
		elif c == curses.KEY_HOME:
			cursor = 0
		elif c == curses.KEY_END:
			cursor = len(lines) - 1
		elif c == curses.KEY_NPAGE:
			cursor += tweets_in_screen
		elif c == curses.KEY_PPAGE:
			cursor -= tweets_in_screen

		if cursor < 0: cursor = 0
		if cursor >= len(lines): cursor = len(lines) - 1

curses.nocbreak()
stdscr.keypad(0)
curses.noecho()
curses.endwin()

f = open(tweets_fname, 'wb')
pickle.dump(tweets, f)
f.close()