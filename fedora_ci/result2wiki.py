#!/usr/bin/env python2

import datetime
import jinja2
import json
import mwclient
import os
import sys
import time

def render_wpage():
    """Generate wiki page file.
    Returns
    -------
    str
        Page to be uploaded to wiki.
    """
    print('Render wiki page')
    try:
        data = json.load(open('result.json'))
    except:
        print("FAIL: Could not read result.json file")
        return None

    delta = int(data['delta'])
    if delta > 3600:
        delta = "%s hours" % (delta / 3600)
    elif delta > 60:
        delta = "%s minutes" % (delta / 60)
    start_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(data['start_time']))

    cdir = os.path.dirname(os.path.abspath(__file__))
    j2_loader = jinja2.FileSystemLoader(cdir)
    j2_env = jinja2.Environment(loader=j2_loader, trim_blocks=True)
    template = j2_env.get_template("wikitemplate.j2")
    template_vars = {'updated': datetime.datetime.utcnow(), 'results': data["results"],
                    'delta': delta, 'start_time': start_time}
    return template.render(template_vars)


def publish():
    base_url = "fedoraproject.org"
    page_name = "CI/Tests/recent_builds"
    page_data = render_wpage()
    if not page_data:
        print("INFO: No result to submit")
        return True
    login = os.environ.get('WIKI_USER')
    passw = os.environ.get('WIKI_PASS')
    ua = 'MyWikiTool/0.2 run by User:FedoraUser'
    site = mwclient.Site(base_url, clients_useragent=ua)
    try:
        site.login(login, passw)
    except:
        print("FAIL: Could not login to %s" % base_url)
        return False
    page = site.pages[page_name]
    if not page.exists:
        print("INFO: Page %s doesn't exist. Creating a new one." % page_name)
    try:
        page.save(page_data, 'Auto updated.')
    except:
        print("FAIL: Could not update %s" % base_url)
        print("dumping wiki data:\n %s" % page_data)
        return False

    return True

if __name__ == "__main__":
    if publish():
        sys.exit(0)
    sys.exit(1)
