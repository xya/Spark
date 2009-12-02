import threading
import time
from spark.async._iocp import CompletionPort, Overlapped

def loop(cp):
    print "Entering loop"
    while True:
        id, tag, bytes, data = cp.wait()
        if len(data) == 0:
            print "Exiting loop"
            break
        else:
            print "%s %s %s %s" % (hex(id), tag, bytes, repr(data))

cp = CompletionPort()
t = threading.Thread(target=loop, args=(cp,))
t.daemon = True
t.start()
time.sleep(0.5)
cp.post("foo", "bar", "baz")
time.sleep(0.5)
cp.post()
t.join()
cp.close()