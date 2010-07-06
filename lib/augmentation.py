'''
Data augmentation services supplied with Zen


'''

import re

from amara.lib import U
from amara.lib.date import timezone, UTC
from amara.thirdparty import json

try:
    from akara import logger
except ImportError:
    logger = None

from zenlib import register_service, zservice
from zenlib.temporal import smart_parse_date
from zenlib.geo import geolookup

import time; from functools import partial; isobase = partial(time.strftime, "%Y-%m-%dT%H:%M:%S")


#def UU(obj, k): return U(obj[k]) if k in obj and obj[k] is not None and U(k).strip() else u''
def UU(obj, k):
    result = U(obj.get(k), noneok=True)
    if result is None:
        return u''
    else:
        return result.strip()


@zservice(u'http://purl.org/com/zepheira/augmentation/location')
def augment_location(source, propertyinfo, augmented, failed):
    '''
    Sample propertyinfo
    {
        "property": "latlong",
        "enabled": true,
        "label": "Mapped place",
        "tags": ["property:type=location"],
        "composite": [
            "street_address",
            "city",
            "state",
            "zip"
        ]
    }
    '''
    composite = propertyinfo[u"composite"]
    pname = propertyinfo.get(u"property", u'location_latlong')
    def each_obj(obj, id):
        address_parts = [ UU(obj, k) for k in composite ]
        if not any(address_parts):
            failed.append({u'id': id, u'label': obj[u'label'],
                            u'reason_': u'No address information found'})
            return
        location = u', '.join(address_parts)
        if logger: logger.debug("location input: " + repr(location))
        location_latlong = geolookup(location)
        if location_latlong:
            augmented.append({u'id': id, u'label': obj[u'label'],
                                pname: location_latlong})
        else:
            failed.append({u'id': id, u'label': obj[u'label'],
                            pname: location, u'reason_': u'No geolocation possible for address'})
    augment_wrapper(source, pname, failed, each_obj, 'augment_location')
    return


def augment_wrapper(source, pname, failed, func, opname):
    for obj in source:
        try:
            id = obj[u'id']
            func(obj, id)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, e:
            if logger: logger.info('Exception in %s: '%opname + repr(e))
            failed.append({u'id': id, u'label': obj[u'label'], pname: repr(e)})


LEN_BASE_ISOFORMAT = 19

@zservice(u'http://purl.org/com/zepheira/augmentation/datetime')
def augment_date(source, propertyinfo, augmented, failed):
    '''
    Sample propertyinfo
    {
        "property": "start_date",
        "enabled": true,
        "label": "Start date",
        "tags": ["property:type=datetime"],
        "composite": [
            "start"
        ]
    }
    '''
    composite = propertyinfo[u"composite"]
    pname = propertyinfo.get(u"property", u'iso_datetime')
    def each_obj(obj, id):
        #Excel will sometimes give us dates as integers, which reflects in the data set coming back.
        #Hence the extra unicode conv.
        #FIXME: should fix in freemix.json endpoint and remove from here
        date_parts = [ unicode(obj[k]) for k in composite if unicode(obj.get(k, u'')).strip() ]
        if not any(date_parts):
            failed.append({u'id': id, u'label': obj[u'label'],
                            pname: u'No date information found'})
            return
        date = u', '.join(date_parts)
        if logger: logger.debug("date input: " + repr(date))
        #FIXME: Think clearly about timezone here.  Consider defaults to come from user profile
        clean_date = smart_parse_date(date)
        if clean_date:
            try:
                augmented.append({u'id': id, u'label': obj[u'label'],
                                    pname: isobase(clean_date.utctimetuple()) + UTC.name})
            except ValueError:
                #strftime cannot handle dates prior to 1900.  See: http://docs.python.org/library/datetime.html#strftime-and-strptime-behavior
                augmented.append({u'id': id, u'label': obj[u'label'],
                                    pname: clean_date.isoformat()[:LEN_BASE_ISOFORMAT] + UTC.name})
        else:
            failed.append({u'id': id, u'label': obj[u'label'],
                            pname: date, u'reason_': u'Unable to parse date'})
    augment_wrapper(source, pname, failed, each_obj, 'augment_date')
    #if logger: logger.info('Exception in augment_date: ' + repr(e))
    return


@zservice(u'http://purl.org/com/zepheira/augmentation/luckygoogle')
def augment_luckygoogle(source, propertyinfo, augmented, failed):
    '''
    '''
    #logger.debug("Not found: " + place)
    composite = propertyinfo[u"composite"]
    pname = propertyinfo.get(u"property", u'luckygoogle')
    for obj in source:
        try:
            objid = obj[u'id']
            #Excel will sometimes give us dates as integers, which reflects in the data set coming back.
            #Hence the extra unicode conv.
            #FIXME: should fix in freemix.json endpoint and remove from here
            item = u', '.join([ unicode(obj[k]) for k in composite if unicode(obj.get(k, u'')).strip() ])
            link = luckygoogle(item)
            if link:
                val = items_dict.setdefault(objid, {u'id': objid, u'label': obj[u'label']})
                val[pname] = link
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, e:
            if logger: logger.info('Exception in augment_date: ' + repr(e))
            failureinfo = failure_dict.setdefault(objid, {u'id': objid, u'label': obj[u'label']})
            failureinfo[pname] = repr(e)
    return


@zservice(u'http://purl.org/com/zepheira/augmentation/shredded-list')
def augment_shredded_list(source, propertyinfo, augmented, failed):
    '''
    See: http://community.zepheira.com/wiki/loc/ValidPatternsList

    >>> from zenlib import augmentation
    >>> source = [{u"id": u"_1", u"label": u"_1", u"orig": u"text, text, text"}]
    >>> propinfo = {u"delimiter": u",", u"extract": u"orig", u"property": u"shredded", u"enabled": True, u"label": "shredded result", u"tags": [u"property:type=text"]}
    >>> result = []
    >>> failed = []
    >>> augmentation.augment_shredded_list(source, propinfo, result, failed)
    >>> result
    [{u'shredded': [u'text', u'text', u'text'], u'id': u'_1', u'label': u'_1'}]

    >>> source = [{u"id": u"_1", u"label": u"_1", u"orig": u"text, text and text"}]
    >>> propinfo = {u"pattern": u"(,)|(and)", u"extract": u"orig", u"property": u"shredded", u"enabled": True, u"label": "shredded result", u"tags": [u"property:type=text"]}
    >>> result = []
    >>> failed = []
    >>> augmentation.augment_shredded_list(source, propinfo, result, failed)
    >>> result
    [{u'shredded': [u'text', u'text', u'text'], u'id': u'_1', u'label': u'_1'}]
    '''
    extract = propertyinfo[u"extract"]
    pname = propertyinfo.get(u"property", u'shreddedlist')
    pattern = propertyinfo.get(u"pattern")
    if pattern: pattern = re.compile(pattern)
    delim = propertyinfo.get(u"delimiter", u',')
    def each_obj(obj, id):
        if pattern:
            text = obj[extract]
            start = 0
            result = []
            #FIXME: Needs to be better spec'ed
            for m in pattern.finditer(text):
                result.append(text[start: m.start()].strip())
                start = m.end() + 1
            result.append(text[start:].strip())
        else:
            result = [ item.strip() for item in obj[extract].split(delim) ]
        if logger: logger.debug("augment_shredded_list: " + repr((obj[extract], pattern, delim)))
        if logger: logger.debug("result: " + repr(result))
        if result:
            augmented.append({u'id': id, u'label': obj[u'label'],
                                pname: result})
    augment_wrapper(source, pname, failed, each_obj, 'augment_shredded_list')
    return
