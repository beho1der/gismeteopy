# -*- coding: utf-8 -*-

from xml.dom import minidom
import urllib, datetime, os, time

from django.conf import settings

import conditions as C

'''
@todo: 1. В классы добавить проверку на DOM
       2. Вывод функций __fmt в _Forecast может быть не верным
       3. Выбрать все объекты с их индексами и адаптировать скрипт под них
'''





class _Town(object):
    
    ATTR_KEYS = ['name', 'id', 'forecasts']
    
    def __init__(self, node):
        self.name = node.getAttribute('sname').encode('cp1251')
        self.name = urllib.unquote(self.name).decode('cp1251')
        self.id = node.getAttribute('index')
        self.forecasts = []
        self.latitude = node.getAttribute('latitude')
        self.longitude = node.getAttribute('longitude')
        for f in node.getElementsByTagName('FORECAST'):
            self.forecasts.append( _Forecast(f) )





class _Forecast(object):
    
    ATTR_KEYS = ['day', 'month', 'year', 'hour', 'tod', 'predict', 'weekday']
    NODES = {
        'PHENOMENA':   ['cloudiness', 'precipitation'],
        'PRESSURE':    ['max', 'min'],
        'TEMPERATURE': ['max', 'min'],
        'WIND':        ['max', 'min', 'direction'],
        'RELWET':      ['max', 'min'],
        'HEAT':        ['max', 'min'],
    }
    DATA = {
        '_chk':     u'Сортер',
        '_picture': u'Изображение',
        '_tod':     u'Время дня',
        '_date':    u'Дата',
        '_phenom':  u'Погода', 
        '_temp':    u'Температура', 
        '_wind':    u'Ветер', 
        '_press':   u'Давление', 
        '_wet':     u'Влажность',
    }
    
    TEMP_IS_AVERAGE = False
    
    
    def __init__(self, node):
        struct = _Forecast.NODES
        for a in _Forecast.ATTR_KEYS:
            setattr(self, a, node.getAttribute(a))
        for p in node.childNodes:
            if p.nodeType == p.ELEMENT_NODE and p.localName in struct.keys():
                tag_name = p.tagName
                for a in struct.get(tag_name):
                    setattr(self, '%s.%s' % (tag_name, a), p.getAttribute(a))
        self.__format()
    
    
    def __format(self):
        for t in _Forecast.DATA.keys():
            getattr(self, '_Forecast__fmt%s' % t)()
    
    
    def __fmt_chk(self):
        setattr(
            self, '_chk', '%s%s%s%s' % (self.year, self.month, self.day, self.tod)
        )
    
    
    def __fmt_picture(self):
        val = self.get('PHENOMENA.cloudiness')\
           or self.get('PHENOMENA.precipitation')\
           or False
        setattr(self, '_picture', C.PICTURE.get(val, 'empty'))
    
    
    def __fmt_tod(self):
        tod = self.get('tod')
        setattr(self, '_tod', C.TOD.get(tod, ''))
    
    
    def __fmt_date(self):
        si = self.safe_int
        t = datetime.date.today()
        year = si(self.get('year')) or t.year
        month = str(si(self.get('month')) or t.month)
        day = si(self.get('day')) or t.day
        weekday = self.get('weekday')
        date = u'%s, %s %s %s' % (
            C.WEEKDAY.get(weekday, ''), day, C.MONTH.get(month, ''), year
        )
        setattr(self, '_date', date)
    
    
    def __fmt_phenom(self):
        s = []
        prec = self.get('PHENOMENA.precipitation')
        prec = C.PRECIPITATION.get(prec)
        if prec: s.append(prec)
        cloud = self.get('PHENOMENA.cloudiness')
        cloud = C.CLOUDINESS.get(cloud)
        if cloud: s.append(cloud)
        setattr(self, '_phenom', u', '.join(s))
            
    
    def __fmt_temp(self):
        def add_plus(n): return u'%s%s' % ('+' if n > 0 else '', n)
        t = ''; tt = []; is_avg = _Forecast.TEMP_IS_AVERAGE 
        nmin = self.get('TEMPERATURE.min')
        nmax = self.get('TEMPERATURE.max')
        if nmin != '':
            tt.append( self.safe_int(nmin) )
        if nmax != '':
            tt.append( self.safe_int(nmax) )
        tt.sort()
        if is_avg and len(tt) == 2:
            aver = (tt[0] + tt[1]) / 2
            t = add_plus(aver)
        elif not is_avg and len(tt) == 2:
            if tt[0] <= 0 and tt[1] <= 0: tt.reverse()
            t = u' '.join(map(add_plus, tt))
        elif not is_avg and len(tt) == 1:
            t = add_plus(tt[0])
        setattr(self, '_temp', u'%s°C' % t)
    
    
    def __fmt_wind(self):
        nmin = self.get('WIND.min')
        nmax = self.get('WIND.max')
        ndir = self.get('WIND.direction')
        setattr(self, '_wind', u'%s %s-%s м/с' % (C.DIRECTION.get(ndir), nmin, nmax))
    
    
    def __fmt_press(self):
        nmin = self.get('PRESSURE.min')
        nmax = self.get('PRESSURE.max')
        setattr(self, '_press', u'%s-%s мм.рт.ст.' % (nmin, nmax))
    
    
    def __fmt_wet(self):
        nmin = self.get('RELWET.min')
        nmax = self.get('RELWET.max')
        setattr(self, '_wet', u'%s-%s%%' % (nmin, nmax))
    
    
    def safe_int(self, n):
        try:
            return int(n)
        except:
            return 0
    
    
    def get(self, key):
        try:
            return getattr(self, key)
        except:
            return ''





class GisMeteoParser(object):
    
    CACHE_PATH = settings.GISMETEO_CACHE_FILEPATH
    #CACHE_PATH = 'D:\\Python\\pro\\testwebpy\\media\\'
    CACHE_FILE = 'gismeteo_cache.xml'
    
    def __init__(self, filename=None, xml=None, url=None, town_id=28367, is_xml=False):
        self.__is_xml = is_xml
        self.__xml = None
        self.__data = []
        if filename:
            self.__xml = minidom.parse(filename)
        elif xml:
            self.__xml = xml
        if not url: # для Тюмени по умолчанию
            url = 'http://informer.gismeteo.ru/xml/%s_1.xml' % town_id
        GisMeteoParser.CACHE_FILE = url.split('/')[-1]
        self.__xml = minidom.parseString(self.__get_from_cache(url))
        self.__xml_parse()
    
    
    def __get_from_cache(self, url):
        cache = os.path.join(GisMeteoParser.CACHE_PATH, GisMeteoParser.CACHE_FILE)
        now = time.mktime(datetime.datetime.now().timetuple())
        if os.path.isfile(cache) and (now - os.path.getmtime(cache) < 3600 * 6):
            return open(cache, 'r').read()
        else:
            return self.__get_from_url(url)
    
    
    def __get_from_url(self, url):
        cache = os.path.join(GisMeteoParser.CACHE_PATH, GisMeteoParser.CACHE_FILE)
        data = None
        try:
            fh = urllib.urlopen(url)
            data = fh.read()
            fh.close()
        except IOError:
            pass
        if data:
            fh = open(cache, 'w')
            print cache
            fh.write(data)
            fh.close()
        return data
    
    
    def __xml_parse(self):
        for t in self.__xml.getElementsByTagName('TOWN'):
            self.__data.append( _Town(t) )
    
    
    def data(self):
        return self.__data
    
    
    def html_for_service(self):
        town = self.__data[0]
        u = [
            u'<h2>Прогноз погоды для %s</h2>' % town.name,
            u'<h4>Предоставлено <a href="http://www.gismeteo.ru/towns/',
            u'%s.htm" title="Gismeteo.ru">Gismeteo.ru</a></h4>' % town.id
        ]
        for f in town.forecasts:
            u.append(u'<hr/><div style="background: url(%simg/gismeteo/%s.png)' % (settings.STATIC_URL, f._picture,))
            u.append(u' no-repeat left top;padding-left:75px;line-height:150%;">')
            u.append(u'<div style="font-weight:bold;font-size:110%%;">%s' % f._tod)
            u.append(u', %s</div>' % f._date)
            u.append(u'<div>%s</div>' % f._phenom)
            u.append(u'<div><b>Температура:</b> %s</div>' % f._temp)
            u.append(u'<div><b>Ветер:</b> %s</div>' % f._wind)
            u.append(u'<div><b>Давление:</b> %s</div>' % f._press)
            u.append(u'<div><b>Влажность:</b> %s</div></div>' % f._wet)
        return u''.join(u)
    
    
    def xml_for_service(self):
        town = self.__data[0]
        u = [
            '<?xml version="1.0" encoding="utf-8"?>', '<data>'
        ]
        for f in town.forecasts:
            u.append('    <row>')
            for a in _Forecast.DATA:
                if a == '_date':
                    key = 'time'
                else:
                    key = a[1:]
                u.append( '        <%s>%s</%s>' % ( key, getattr(f, a), key ) )
            u.append('    </row>')
        u.append('</data>')
        return u'\n'.join(u)





if __name__ == '__main__':
    #gmp = GisMeteoParser(filename='28367_1.xml')
    gmp = GisMeteoParser(url='http://informer.gismeteo.ru/xml/28367_1.xml')
    #print gmp.html_for_service()
    print gmp.xml_for_service()