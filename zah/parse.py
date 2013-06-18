from datetime import datetime 

from bs4 import BeautifulSoup

class ZAHansardParser(object):

    def parse(self, html):
        soup = BeautifulSoup(html)

        title = soup.find('h1', class_ = 'title').string
        node = soup.find('div', class_ = 'node')
        # taxonomy?
        content = node.find('div', class_ = 'content')

        dt = content.find('div', class_='field-field-meeting-date')
        date_string = dt.get_text('', strip=True)
        date = datetime.strptime( dt.find('span', class_ = 'date-display-single').get_text('', strip=True), '%d %b %Y' )

        return {
                'title': title,
                'date_string' : date_string,
                'date' : date,
                }

