import json
import logging
import signal

from sprockets.mixins.mediatype import content
from tornado import ioloop, web
import msgpack


class SimpleHandler(content.ContentMixin, web.RequestHandler):

    def post(self):
        body = self.get_request_body()
        self.set_status(200)
        self.send_response(body)
        self.finish()


def make_application(**settings):
    application = web.Application([web.url(r'/', SimpleHandler)], **settings)
    content.set_default_content_type(application, 'application/json',
                                     encoding='utf-8')
    content.add_binary_content_type(application, 'application/msgpack',
                                    msgpack.packb, msgpack.unpackb)
    content.add_text_content_type(application, 'application/json', 'utf-8',
                                  json.dumps, json.loads)
    return application


def _signal_handler(signo, _):
    logging.info('received signal %d, stopping application', signo)
    iol = ioloop.IOLoop.instance()
    iol.add_callback_from_signal(iol.stop)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)1.1s - %(name)s: %(message)s')
    application = make_application(debug=True)
    application.listen(8000)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    ioloop.IOLoop.instance().start()
