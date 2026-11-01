"""Check the built archive's domain and crawler directives."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.robots = set()
        self.canonicals = []
        self.feeds = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name', '').lower() == 'robots':
            self.robots.update(s.strip() for s in attrs.get('content', '').lower().split(','))
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs.get('href', ''))
        if tag == 'link' and attrs.get('type') in ('application/rss+xml', 'application/atom+xml'):
            self.feeds.append(attrs.get('href'))


def check(site, domain):
    errors = []
    robots_file = site / 'robots.txt'
    if not robots_file.exists():
        errors.append('robots.txt missing')
    else:
        robots = RobotFileParser()
        text = robots_file.read_text()
        robots.parse(text.splitlines())
        for agent in ('Googlebot', 'bingbot', 'GPTBot', 'ClaudeBot', 'unknown-crawler'):
            for path in ('/', '/posts', '/post/example', '/assets/img/example.png'):
                if robots.can_fetch(agent, 'https://' + domain + path):
                    errors.append(f'robots.txt allows {agent} {path}')
        if 'sitemap:' in text.lower():
            errors.append('robots.txt advertises a sitemap')
    cname = site / 'CNAME'
    if not cname.exists() or cname.read_text().strip() != domain:
        errors.append('CNAME does not match archive domain')
    for name in ('sitemap.xml', 'sitemap.xml.gz', 'feed.xml'):
        if (site / name).exists():
            errors.append(f'{name} still generated')
    pages = list(site.rglob('*.html'))
    if not pages:
        errors.append('no HTML pages built')
    for path in pages:
        head = Head()
        head.feed(path.read_text())
        if not {'noindex', 'nofollow', 'noarchive', 'nosnippet', 'noimageindex'} <= head.robots:
            errors.append(f'{path.relative_to(site)} missing restrictive robots metadata')
        if len(head.canonicals) != 1 or urlparse(head.canonicals[0]).netloc != domain:
            errors.append(f'{path.relative_to(site)} has incorrect canonical domain')
        if head.feeds:
            errors.append(f'{path.relative_to(site)} advertises a feed')
    assert not errors, '\n'.join(errors)
    print(f'Archive checks passed: {len(pages)} HTML pages, {domain}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, default=Path('_site'))
    parser.add_argument('--domain', required=True)
    args = parser.parse_args()
    check(args.site_dir, args.domain)
