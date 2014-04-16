#!/usr/bin/env python

import sys
import os
import re
import urllib2
from urlparse import urlparse, urljoin
from bs4 import BeautifulSoup


BASE_URL = 'https://developers.google.com/analytics'


def main():
    '''
    Crawl dev site for goo.gl links
    '''

    visited_links = []
    queued_links = []
    found = []

    queued_links.append(BASE_URL)

    print "Starting crawl of %s" % BASE_URL

    while len(queued_links) > 0:
        url = queued_links.pop()
        visited_links.append(url)

        # print "Searching %s" % url
        sys.stdout.write('.')
        sys.stdout.flush()
        try:
            request = urllib2.Request(url)
            response = urllib2.urlopen(request)
        except:
            continue

        if 'html' not in response.info().gettype().lower():
            continue

        page = response.read()

        if "goo.gl/" in page:
            locations = [m.start() for m in re.finditer('goo.gl/', page)]
            for pos in locations:
                x = page[pos:pos + 13]
                if x in found:
                    print "\n%s" % x
                else:
                    print "\n\033[91m%s\033[0m" % x
                    found.append(x)

        soup = BeautifulSoup(page)
        for a in soup.find_all('a'):
            href = a.get('href')
            if href:
                link = resolve_relative(href)
                if link not in visited_links and \
                    link not in queued_links and \
                    is_interesting(link):

                    queued_links.append(link)

    print "\n\n**** SUMMARY ****"
    for x in sorted(set(found)):
        print "\033[94m%s\033[0m" % x


def is_interesting(link):

    o = urlparse(link)

    if link.startswith('//') or \
        o.scheme == '' or \
        o.netloc.lower() != 'developers.google.com' or \
        not o.path.lower().startswith('/analytics'):

        return False
    else:
        return True


def resolve_relative(link):
    '''
    Resolve relative URL, remove query and fragment.
    '''

    o = urlparse(link)

    if o.netloc == '':
        link = urljoin(BASE_URL, link)

    if o.fragment != '':
        link = link.partition('#')[0]

    if o.query != '':
        link = link.partition('?')[0]

    return link


if __name__ == '__main__':
    main()
