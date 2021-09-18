import logging
import signal
import typing

from sprockets.mixins.mediatype import content, transcoders
from tornado import ioloop, web


class SimpleHandler(content.ContentMixin, web.RequestHandler):
    def post(self) -> None:
        body = self.get_request_body()
        self.set_status(200)
        self.send_response(body)


def make_application(**settings: typing.Any) -> web.Application:
    application = web.Application([('/', SimpleHandler)], **settings)
    content.set_default_content_type(application,
                                     'application/json',
                                     encoding='utf-8')
    content.add_transcoder(application, transcoders.MsgPackTranscoder())
    content.add_transcoder(application, transcoders.JSONTranscoder())
    return application


def _signal_handler(signo: int, _: typing.Any) -> None:
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
