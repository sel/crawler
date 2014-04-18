#!/usr/bin/env python

import sys
import os
import re
import urllib2
import json
import optparse
import requests
import base64
import binascii
from optparse import OptionParser
from urlparse import urlparse, urljoin
from bs4 import BeautifulSoup


DEBUG_LEVEL = 0


def main():
    parser = OptionParser("%prog [options] FIRST_PATH_SEGMENT\n")
    parser.add_option("-y", "--no-youtube", action="store_true",
                      dest="skip_youtube", help="Skip youtube channels")
    parser.add_option("-s", "--no-hash-search", action="store_true",
                      dest="skip_hashes", help="Skip searching for hashed links")
    parser.add_option("-d", "--no-devsite", action="store_true",
                      dest="skip_devsite", help="Skip searching devsite.  Implies -s")

    parser.add_option("-n", "--new-only", action="store_true",
                      dest="log_new_only", help="Log new links only.")

    (options, args) = parser.parse_args()

    HTML_BASE_URL = 'http://developers.google.com/'

    if len(args) > 0:
        root = HTML_BASE_URL + args[0]
    else:
        root = HTML_BASE_URL + 'analytics'

    crawl(root, options.skip_youtube,
          options.skip_hashes, options.skip_devsite, options.log_new_only)


def crawl(root, skip_youtube, skip_hashes, skip_devsite, log_new_only):
    '''
    Crawl dev site and youtube channels for plain and hashed goo.gl links
    '''

    already_found = json.load(open("found.json", 'r'))
    new_found = []

    already_found_hash = json.load(open("found_hashed.json", 'r'))
    new_found_hash = []

    if DEBUG_LEVEL > 0:
        print "All already found links:"
        print json.dumps(already_found, sort_keys=True, indent=4)

    if not skip_youtube:
        new_found, already_found = crawl_youtube(already_found, log_new_only)

        if len(new_found) > 0:
            print "\n\n**** YOUTUBE: newly found ****"
            for x in sorted(set(new_found)):
                print "\033[94m%s\033[0m" % x

    if not skip_devsite:
        new_found, already_found, new_found_hash, already_found_hash = craw_devsite(
            root, already_found, already_found_hash, skip_hashes, log_new_only)

        if len(new_found) > 0:
            print "\n\n**** DEVSITE: newly found ****"
            for x in sorted(set(new_found)):
                print "\033[94m%s\033[0m" % x

        if not skip_hashes:
            if len(new_found_hash) > 0:
                print "\n\n**** DEVSITE: newly found hashed links ****"
                for x in sorted(set(new_found_hash)):
                    print "\033[94m%s\033[0m" % x

        if not log_new_only:
            print "All already found links:"
            print json.dumps(already_found, sort_keys=True, indent=4)

        with open('found2.json', 'w') as outfile:
            json.dump(already_found, outfile, sort_keys=True, indent=4)

        if not skip_hashes:
            if not log_new_only:
                print "All already found hashed links:"
                print json.dumps(already_found_hash, sort_keys=True, indent=4)

            with open('found_hashed2.json', 'w') as outfile:
                json.dump(
                    already_found_hash, outfile, sort_keys=True, indent=4)


def crawl_youtube(already_found, log_new_only):
    new_found = []

    ANDROID_DEV_YOUTUBE = 'https://www.youtube.com/user/androiddevelopers/videos'
    GOOGLE_DEV_YOUTUBE = 'https://www.youtube.com/user/GoogleDevelopers/videos'
    ANNOTATIONS_URL_BASE = 'https://www.youtube.com/annotations_invideo?features=1&legacy=1&video_id='

    for channel in [ANDROID_DEV_YOUTUBE, GOOGLE_DEV_YOUTUBE]:
        videos = []

        print "\nStarting crawl of %s" % channel

        page = urllib2.urlopen(channel).read()
        soup = BeautifulSoup(page)
        for a in soup.find_all('a'):
            href = a.get('href')
            if href and href.startswith("/watch?v="):
                v = href[9:]

                if DEBUG_LEVEL > 0:
                    print "Found video %s" % v
                elif not log_new_only:
                    sys.stdout.write('.')
                    sys.stdout.flush()

                page = urllib2.urlopen(ANNOTATIONS_URL_BASE + v).read()

                new_found, already_found = find_googl_links(
                    page, already_found, new_found, log_new_only)

    return new_found, already_found


def craw_devsite(root, already_found, already_found_hash, skip_hashes, log_new_only):

    visited_links = []
    queued_links = []
    new_found = []
    new_found_hash = []

    queued_links.append(root)

    print "\nStarting crawl of %s" % root

    while len(queued_links) > 0:
        url = queued_links.pop()
        visited_links.append(url)

        if DEBUG_LEVEL > 0:
            print "Searching %s" % url
        elif not log_new_only:
            sys.stdout.write('.')
            sys.stdout.flush()

        try:
            request = urllib2.Request(url)
            response = urllib2.urlopen(request)
        except Exception, e:
            if DEBUG_LEVEL > 0:
                print "Exception reading %s:\n%s" % (url, e)
            continue

        content_type = response.info().gettype().lower()
        if 'html' not in content_type and 'xml' not in content_type:
            if DEBUG_LEVEL > 0:
                print "Not html content type at %s" % url
            continue

        page = response.read()

        new_found, already_found = find_googl_links(
            page, already_found, new_found, log_new_only)

        if not skip_hashes:
            new_found_hash, already_found_hash = find_hashed_googl_links(
                page, already_found_hash, new_found_hash, log_new_only)

        soup = BeautifulSoup(page)
        for a in soup.find_all('a'):
            href = a.get('href')
            if href:
                link = resolve_relative(href, root)
                if link not in visited_links and \
                    link not in queued_links and \
                    is_interesting_devsite_link(link, root):

                    queued_links.append(link)

    return new_found, already_found, new_found_hash, already_found_hash


def find_googl_links(page, already_found, new_found, log_new_only):
    locations = [m.start() for m in re.finditer('goo.gl/', page)]
    for pos in locations:
        x = page[pos:pos + 13]
        if is_lucky_redirect(x):
            if x not in already_found:
                log_link_found(x)
                new_found.append(x)
                already_found.append(x)
            elif not log_new_only:
                print "\n%s" % x

    return new_found, already_found


def find_hashed_googl_links(page, already_found_hash, new_found_hash, log_new_only):
    b64_pattern = re.compile(
        r'(?:[A-Za-z0-9+/]{4}){2,}(?:[A-Za-z0-9+/]{2}[AEIMQUYcgkosw048]=|[A-Za-z0-9+/][AQgw]==)')

    for m in b64_pattern.finditer(page):
        x = page[m.start():m.end()]
        if len(x) == 28:
            if x not in already_found_hash:
                log_link_found(x)
                new_found_hash.append(x)
                already_found_hash.append(x)

                decoded_bytes = base64.b64decode(x)
                print binascii.hexlify(decoded_bytes)
            elif not log_new_only:
                print "\n%s" % x

        elif DEBUG_LEVEL > 0:
            print "not matched: %s" % x

    return new_found_hash, already_found_hash


def log_link_found(link):
    sys.stdout.write("\a")  # BEEP
    print "\n\033[91m%s\033[0m" % link


def is_lucky_redirect(url):
    TICKET_BASE = 'http://developers.google.com/events/io/2014/redeem/'
    resp = requests.head('http://' + url)
    location = resp.status_code == 301 and resp.headers['location'] or ''
    lucky = location.startswith(TICKET_BASE)

    if not lucky and DEBUG_LEVEL > 0:
        print "No joy with %s -> %s" % (url, location)

    return lucky


def is_interesting_devsite_link(link, root):
    b = urlparse(root)
    o = urlparse(link)

    if link.startswith('//') or \
        o.scheme == '' or \
        o.netloc.lower() != b.netloc.lower() or \
        not o.path.lower().startswith(b.path.lower()):

        return False
    else:
        return True


def resolve_relative(link, root):
    '''
    Resolve relative URL, remove query and fragment.
    '''

    o = urlparse(link)

    if o.netloc == '':
        link = urljoin(root, link)

    if o.fragment != '':
        link = link.partition('#')[0]

    if o.query != '':
        link = link.partition('?')[0]

    return link


if __name__ == '__main__':
    main()
