#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler,HTTPServer
from datetime import datetime
import socketserver, threading, time
try:
    import urlparse
except ImportError:
    from urllib.parse import urlparse,parse_qs
import pymysql
from contextlib import closing

urlServiceReportPositions = "/gps/"
nameClientDB = 'clients'
ipServerStream = '127.0.0.1'
portServer = 8001
portHTTP = 8080
userDB = 'admin'
passwordDB = 'admin'
# GPS service

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def __init__(self, request, client_address, server):
       self.server_address = server.server_address
       self.id_message = 100
       self.kill_received = False
       socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    # unpack messages
    def unpack_data(self, data, _device_id, _batt, _gps):
        message = ''
        device_id = _device_id
        #print('TCP:{}'.format(data))
        batt = _batt
        gps = _gps
        arr_data = data.decode('utf-8').split(']')
        #print(arr_data)
        mess_send = None
        with closing(pymysql.connect('localhost','admin','admin','clients')) as mySqlConnect:
            with mySqlConnect.cursor() as myCursor:
                for arr_data_i in arr_data:
                    if arr_data_i != '': 
                        mess = arr_data_i.split(',')
                        #print(mess)
                        mess_dev = mess[0][1:]
                        #print(mess_dev)
                        net_dev = mess_dev.split('*')
                        #print(net_dev)
                        device_id = net_dev[1]
                        if net_dev[3] == 'LK':
                            batt = int(mess[3])
                            gps = int(mess[1])
                            # b'[3G*ID*0002*LK][3G*ID*0008*REMOVE,1]' 
                            # b'[3G*ID*0002*LK][3G*ID*0006*PEDO,1]' 
                            # b'[3G*ID*0016*REMIND,8:0-1-3-0000000]'
                            # b'[3G*ID*0002*LK][3G*ID*0008*FLOWER,2]'
                            mess_send = bytes('[3G*{0}*0002*LK][3G*{0}*0006*PEDO,1]'.format(device_id),'utf-8')
                        if net_dev[3] == 'TKQ':
                            mess_send = data
                        if net_dev[3] == 'TKQ2':
                            mess_send = data
                        elif net_dev[3] == 'UD2' or net_dev[3] == 'UD':
                            date_dev = mess[1]
                            time_dev = mess[2]
                            lat_dev  = mess[4]
                            lon_dev  = mess[6]
                            dt_dev = date_dev[4:6]+"20-"+date_dev[2:4]+"-"+date_dev[0:2]+" "+time_dev[0:2]+":"+time_dev[2:4]+":"+time_dev[4:6]
                            query = 'INSERT INTO `gpsdb` (`deviceid`,`devicemessage`,`gps`,`vbattery`,`lon`,`lat`,`dt`,`speed`,`dim`,`typemsg`)'
                            query += 'VALUES ("{0}","{1}","{2}","{3}","{4}","{5}","{6}",{7},{8},"{9}");'.format(device_id,'',gps,batt,lon_dev,lat_dev,dt_dev,0,0,net_dev[3])
                            try: 
                                myCursor.execute(query)
                                mySqlConnect.commit()
                            except pymysql.InternalError as error:
                                # notFindClientDB = True
                                m_code, m_message = error.args
                                print('MySQL Error [{0}]:{1}\n\r {2}'.format(m_code,m_message,query))

                            #print(query)
                        else:
                            print(net_dev)
                        #print(mess_dev)
        return device_id, batt, gps, mess_send
        
 

    def handle(self):
        current_thread = threading.current_thread()
        print("TCP Server {}:".format(self.server_address))
        try:
            device_id = ''
            batt = 0
            gps = 0
            while not self.kill_received:
                response = b''
                data = self.request.recv(1024)
                if self.server_address[1] == 8001:
                   if len(data) > 0:
                       print('{0}:{1}'.format(self.client_address, data))
                       device_id, batt, gps, mess_send = self.unpack_data(data, device_id, batt, gps)
                       if not (mess_send is None):
                           self.request.sendall(mess_send)
                else:
                   print('Ready {0}'.format(self.client_address))
            self.client.close()
            print('End while!')
        except Exception as e:
            print(e.__class__)
            print("Error send data:{}".format(data))
            self.request.close()
            exit(0)
        finally:
            self.request.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    deamon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
	#print('Start service TCP:{}'.format(server_address))
        self.servre_address1 = server_address
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass)

    pass


def create_srv_tcp(port):
    print("Init TCP server:{}".format(port))
    server_t = ThreadedTCPServer(("0.0.0.0", port), ThreadedTCPRequestHandler)
    server_thr = threading.Thread(target=server_t.serve_forever)
    server_thr.daemon = True
    return server_thr


# Web services
class HttpProcessor(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            curl = urlparse(self.path)
        except:
            print("error:{}".format(self.path))
            return

        print('url:{}'.format(curl))
        if curl.path == urlServiceReportPositions:
            curlParams = parse_qs(curl.query)
            iddevice = curlParams.get('device',None)
            if iddevice != None:
                iddevice = iddevice[0]
            else:
                self.send_response(501)
                self.send_header('Server','spaceNet-Host/1.0')
                self.send_header('Content-type','text/html')
                self.end_headers()
                self.wfile.write(b'Error service!')
                return
            print(iddevice)
            self.send_response(200)
            self.send_header('content-type','text/html')
            self.send_header('Connection','close')
            self.end_headers()
            #self.wfile.write("Ok !")
            tracker = ''
            last_lon = '47.271862'
            last_lat = '39.759238'
            last_dt = ''
            vbatt = ''
            with closing(pymysql.connect('localhost','admin','admin',nameClientDB)) as mySqlConnect:
                with mySqlConnect.cursor() as myCursor:
                    myCursor.execute("select `lon`,`lat`,`dt`,`vbattery` from gpsdb where dt <= NOW() and `deviceid` = '{0}' order by `dt` desc limit 1 ;".format(iddevice))
                    if not myCursor.rowcount == 0:
                        row_posit = myCursor.fetchone()
                        last_lon = row_posit[0]
                        last_lat = row_posit[1]
                        last_dt = row_posit[2]
                        vbatt = row_posit[3]
            http_body ='''<!DOCTYPE html>
	        <head>
                   <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
                   <meta http-equiv="X-UA-Compatible" content="IE=9"/>
                   <link rel="stylesheet" href="https://unpkg.com/leaflet@1.5.1/dist/leaflet.css" />
                   <script src="https://unpkg.com/leaflet@1.5.1/dist/leaflet.js"></script>
	        </head>
	        <body>
                   <form name="form" method="get" style="visibility:hidden; height:0px; background-color:#FF0000;">
                    <input name="result" type="hidden" value=" " />
                    <input id="event_to_1c" name="event_to_1c" type="hidden" value=" " />
                   </form>
                   '''
            http_body += '<div id="status" class="status" style="position: absolute; top: 0px; right: 0px; bottom: 0px; left: 0px;">Уровень аккумулятора:'+str(vbatt)+'%\n\rПоследнии данные:'+last_dt.isoformat()+'</div>'
            http_body += ''' <div id="map" class="map" style="position: absolute; top: 100px; right: 0px; bottom: 0px; left: 0px;"></div>
                   <script type="text/javascript">
    	             var map = L.map('map');
                     '''
            http_body += 'map.setView([{1}, {0}], 16);'.format(last_lon,last_lat)
            http_body +="""
                     L.tileLayer('http://{s}.tile.osm.org/\{z\}/\{x\}/\{y\}.png', {
    		       attribution: '&copy; <a href="/redirect.php?url=aHR0cDovL29zbS5vcmcvY29weXJpZ2h0">OpenStreetMap</a> and &copy; <a href="/redirect.php?url=aHR0cHM6Ly9zaXJpdXMuc3U=">sirius.su</a> contributors'
		     }).addTo(map);
                        """
            # [47.425818,40.0452733]
            route = ''
            with closing(pymysql.connect('localhost','admin','admin',nameClientDB)) as mySqlConnect:
                with mySqlConnect.cursor() as myCursor:
                    myCursor.execute("select `lon`,`lat`,`dt` from `gpsdb` where `dt` >= (DATE(NOW())-1) and `deviceid` = '{0}' order by `dt` asc ;".format(iddevice))
                    print("select `lon`,`lat`,`dt` from `gpsdb` where `dt` >= (DATE(NOW())-1) and `deviceid` = '{0}';".format(iddevice))
                    if not myCursor.rowcount == 0:
                        print( myCursor.rowcount)
                        rr = ''
                        for row_posit in myCursor:
                            if rr =='':
                                rr = "[" +row_posit[1] +","+row_posit[0]  + "]"
                            else:
                                rr += ",[" +row_posit[1] +","+row_posit[0]  + "]"
                        route += "var altlatlngs = [" +rr+ "];"
                        
                        route +=" var altpolyline = L.polyline(altlatlngs, {color: 'blue', weight: 5, opacity: 0.7}).addTo(map);"
                        route += "map.fitBounds(altpolyline.getBounds());"
            http_body +=route+"\n\r"
            http_body +="L.marker(["+last_lat+","+last_lon+"],{title: 'Последнее местоположене'}).addTo(map);\n\r"
            http_body +="""
                     map.on('click',function(evt){
				var input = document.getElementById('event_to_1c');
				input.value = evt.latlng;
			});
		     form.execJS = function (jscode){
			try{
				window.eval(jscode);
				} catch(err) {alert(err);};
			};
                   </script>
	        </body>
                </html>
                 """
            #http_body += http_body2
            self.wfile.write(http_body.encode('utf-8'))

        else:
            try:
                self.send_response(501)
                self.send_header('Server','spaceNet-Host/1.0')
                self.send_header('Content-type','text/html')
                self.end_headers()
                self.wfile.write(b'Error service!')
                # self.wfile.write('{}'.format(curl).encode('utf-8'))
            except ConnectionResetError:
               print("==> ConnectionResetError")
            except timeout:
               print("==> Timeout")
def configDB():
    with closing(pymysql.connect('localhost',userDB,passwordDB,'')) as mySqlConnect:
        with mySqlConnect.cursor() as myCursor:
            # Create DB 
            myCursor.execute('SHOW DATABASES;')
            listDB = myCursor.fetchall()
            notClientDB = True
            for thisDB in listDB:
                if thisDB[0] == nameClientDB:
                    notClientDB = False
                    break
            if notClientDB:
                try:
                    myCursor.execute('CREATE DATABASE `{}`'.format(nameClientDB))
                    print('Create database:{}'.format(nameClientDB))
                except pymysql.InternalError as error:
                    code, message = error.args
                    print('MySQL Error [{0}]:{1}'.format(code,message))
            # Create tables 
            myCursor.execute('USE {};'.format(nameClientDB))
            # Таблица текущего состояния устройства
            myCursor.execute('SHOW TABLES LIKE "devices";')
            if myCursor.rowcount == 0:
               myCursor.execute("""
                   CREATE TABLE `devices` (
                      `deviceid` VARCHAR(64) NOT NULL COLLATE 'utf8_bin',
                      `ICCID` VARCHAR(128) NOT NULL COLLATE 'utf8_bin',
                      `gps` INT(3) NOT NULL ,
                      `dt` DATETIME NOT NULL,
                      `vbattery` INT(3) NOT NULL,
                      `typemsg` VARCHAR(32) NOT NULL COLLATE 'utf8_bin',
                      `lastdt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ) COLLATE='utf8_bin' ENGINE=InnoDB;
               """)

            myCursor.execute('SHOW TABLES LIKE "gpsdb";')
            if myCursor.rowcount == 0:
               myCursor.execute("""
                   CREATE TABLE `gpsdb` (
                      `deviceid` VARCHAR(64) NOT NULL COLLATE 'utf8_bin',
                      `devicemessage` VARCHAR(128) NOT NULL COLLATE 'utf8_bin',
                      `gps` INT(3) NOT NULL ,
                      `dt` DATETIME NOT NULL,
                      `vbattery` INT(3) NOT NULL,
                      `lon` FLOAT NOT NULL ,
                      `lat` FLOAT NOT NULL ,
                      `speed` FLOAT NOT NULL,
                      `dim` FLOAT NOT NULL ,
                      `typemsg` VARCHAR(32) NOT NULL COLLATE 'utf8_bin',
                      `lastdt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ) COLLATE='utf8_bin' ENGINE=InnoDB;
               """)


if __name__ == "__main__":
    print("Start mGPS service")
    # update database
    configDB()
    server8001 = create_srv_tcp(portServer) 
    serv = HTTPServer(("0.0.0.0",portHTTP),HttpProcessor)
    try:
        server8001.start()
        print("Server started ")
        serv.serve_forever()
        while True:
             time.sleep(100)
    except (KeyboardInterrupt, SystemExit):
        server8001.kill_received = True
        # server_item.shutdown()
        # server_item.server_close()
        exit()
