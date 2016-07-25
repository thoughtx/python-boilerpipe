import jpype
import urllib2
import socket
import charade
import threading

socket.setdefaulttimeout(15)
lock = threading.Lock()

InputSource        = jpype.JClass('org.xml.sax.InputSource')
StringReader       = jpype.JClass('java.io.StringReader')
HTMLHighlighter    = jpype.JClass('de.l3s.boilerpipe.sax.HTMLHighlighter')
BoilerpipeSAXInput = jpype.JClass('de.l3s.boilerpipe.sax.BoilerpipeSAXInput')
YoutbeVideo        = jpype.JClass('de.l3s.boilerpipe.document.YoutubeVideo')
VimeoVideo         = jpype.JClass('de.l3s.boilerpipe.document.VimeoVideo')
ImageClass         = jpype.JClass('de.l3s.boilerpipe.document.Image')

class Extractor(object):
    """
    Extract text. Constructor takes 'extractor' as a keyword argument,
    being one of the boilerpipe extractors:
    - DefaultExtractor
    - ArticleExtractor
    - ArticleSentencesExtractor
    - KeepEverythingExtractor
    - KeepEverythingWithMinKWordsExtractor
    - LargestContentExtractor
    - NumWordsRulesExtractor
    - CanolaExtractor
    """
    extractor = None
    source    = None
    data      = None
    headers   = {'User-Agent': 'Mozilla/5.0'}

    def __init__(self, extractor='DefaultExtractor', **kwargs):
        if kwargs.get('url'):
            request     = urllib2.Request(kwargs['url'], headers=self.headers)
            connection  = urllib2.urlopen(request)
            self.data   = connection.read()
            encoding    = connection.headers['content-type'].lower().split('charset=')[-1]
            if encoding.lower() == 'text/html':
                encoding = charade.detect(self.data)['encoding']
            self.data = unicode(self.data, encoding)
        elif kwargs.get('html'):
            self.data = kwargs['html']
            if not isinstance(self.data, unicode):
                self.data = unicode(self.data, charade.detect(self.data)['encoding'])
        else:
            raise Exception('No text or url provided')

        try:
            # make it thread-safe
            if threading.activeCount() > 1:
                if jpype.isThreadAttachedToJVM() == False:
                    jpype.attachThreadToJVM()
            lock.acquire()

            self.extractor = jpype.JClass(
                "de.l3s.boilerpipe.extractors."+extractor).INSTANCE
        finally:
            lock.release()

        reader = StringReader(self.data)
        self.source = BoilerpipeSAXInput(InputSource(reader)).getTextDocument()
        self.extractor.process(self.source)

    def getText(self):
        return self.source.getContent()

    def getHTML(self):
        highlighter = HTMLHighlighter.newExtractingInstance()
        return highlighter.process(self.source, self.data)

    def getMedia(self):
        extractor = jpype.JClass(
            "de.l3s.boilerpipe.sax.MediaExtractor").INSTANCE
        try:
            medias = extractor.process(self.source, self.data)
        except:
            return self.getImages()
        medias = [
            {
                'src'   : media.getSrc(),
                'type'  : 'image',
                'width' : media.getWidth(),
                'height': media.getHeight(),
                'alt'   : media.getAlt(),
                'area'  : media.getArea()
            } if type(media) is ImageClass else {'src': media.getEmbedUrl(), 'type': 'video'} for media in medias
        ]

        return medias



    def getImages(self):
        extractor = jpype.JClass(
            "de.l3s.boilerpipe.sax.ImageExtractor").INSTANCE
        images = extractor.process(self.source, self.data)
        jpype.java.util.Collections.sort(images)
        images = [
            {
                'src'   : image.getSrc(),
                'width' : image.getWidth(),
                'height': image.getHeight(),
                'alt'   : image.getAlt(),
                'area'  : image.getArea()
            } for image in images
        ]
        return images

    def getVideos(self):
        extractor = jpype.JClass(
            "de.l3s.boilerpipe.sax.MediaExtractor").INSTANCE
        videos = extractor.process(self.source, self.data)
        videos = [
            {
                'src': video.getEmbedUrl()
            } for video in videos if type(video) is YoutbeVideo or type(video) is VimeoVideo
        ]
        return videos

    def getOpenGraph(self):
        extractor = jpype.JClass(
            "de.l3s.boilerpipe.sax.OpenGraphExtractor").INSTANCE
        OpenGraphTags = extractor.process(self.source, self.data)
        OpenGraphTags = {key: OpenGraphTags[key] for key in OpenGraphTags}
        return OpenGraphTags

    def getTextDocument(self):
        return self.source

    def getFormattedHTML(self):
        media = self.getMedia()
        html = self.data
        prev = 0
        result = ''
        for m in media:
            src = m.get('src')
            sliced_html = html[prev:html.find(src)]
            prev = html.find(src)
            sliced_html = sliced_html[sliced_html.find('>')+1:]
            try:
                sliced_extractor = Extractor(extractor='ArticleExtractor', html=sliced_html)
                sliced_text = sliced_extractor.getText()
            except:
                if m.get('type') == 'image':
                    result += '<CENTER><IMG SRC="{0}"></CENTER>'.format(src)
                else:
                    result += '<iframe src="{0}" width="420" height="320" frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>'.format(src)
                continue
            result += '<p>'+sliced_text+'</p>'
            if m.get('type') == 'image':
                result += '<CENTER><IMG SRC="{0}"></CENTER>'.format(src)
            else:
                result += '<iframe src="{0}" width="420" height="320" frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>'.format(src)
        sliced_html = html[prev:]
        sliced_html = sliced_html[sliced_html.find('>')+1:]
        sliced_extractor = Extractor(extractor='ArticleExtractor',
                                     html=sliced_html)
        sliced_text = sliced_extractor.getText()
        result += '<p>'+sliced_text+'</p>'
        return result
