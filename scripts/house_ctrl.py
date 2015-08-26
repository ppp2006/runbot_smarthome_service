#encoding=utf-8

import socket
import sys
import struct
import sqlite3
import time
import os

HOST = '192.168.0.151'
PORT = 5005              # The same port as used by the server
MAX_BUF_SZ = 64 * 1024
MAX_TCP_SZ = 1448
MAX_DEV_TYPE_NUM = 64
MAX_CTRL_TYPE_NUM = 16

CMD_LOGON_REQ = 0x4a
CMD_LOGON_RSP = 0x46
CMD_GET_DB_REQ = 0x4c
CMD_GET_DB_RSP = 0x43
CMD_SINGLE_CTRL_REQ = 0x33
CMD_SINGLE_CTRL_RSP = 0x33

OP_MODE_QUERY = 0x07
OP_MODE_ZIG = 0x03
OP_MODE_IR  = 0x04

tbl_app = {}

LOG_ON = False

def init_appliance_tbl(tbl):
    #普通灯
    tbl['0'] = {'0':
                 {'req':{u'开':0x4f, u'关':0x4f},
                 'rsp':{u'开':100, u'关':0}},
    #可调节灯
                '1':
                 {'req':{u'开':0x01, u'关':0x00, u'加':0x03, u'减':0x04},
                 'rsp':{u'开':100, u'关':0, u'加':range(1,100), u'减':range(1,100)}}
               }
    #窗帘
    tbl['1'] = {'3':
                 {'req':{u'开':61, u'关':62, u'暂停':63},
                 'rsp':{u'开':100, u'关':0, u'暂停':50}}
               }
    #电视
    tbl['2'] = {'4':
                 {'req':{u'开':0x00, u'关':0x01, u'频道加':15, u'频道减':16}}
               }


def HAS_DB():
    try:
        stat_info = os.stat('house.sqlite')
    except OSError:
        return False

    st_ctime = stat_info[-1]

    create_date = time.strftime('%Y-%m-%d', time.localtime(st_ctime))
    current_date = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    if current_date > create_date:
        return False   #old beyond 1 day, need update
    else:
        return True


def connect_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    return s

def disconnect_server(s):
    s.close()
    time.sleep(0.1) #ensure socket reclaimed

def logon_server():
    global LOG_ON
    s = connect_server()

    cmd = CMD_LOGON_REQ
    len_pwd = 6
    pwd = '123456'
    tx_buf = struct.pack('<II6s', cmd, len_pwd, pwd) # the ucot server 's byte order is't network !!!
    s.sendall(tx_buf)

    rx_buf = s.recv(MAX_BUF_SZ)
    print 'response msg received: %d bytes' % len(rx_buf)
    cmd_resp, len_data, success = struct.unpack('<IIB', rx_buf)

    disconnect_server(s)
    if 0x01 == success:
        print 'logon success'
        LOG_ON = True
    else:
        print 'logon failed'

def get_house_db():
    if not LOG_ON:
        logon_server()

    s = connect_server()

    cmd = CMD_GET_DB_REQ
    tx_buf = struct.pack('<I', cmd)
    print 'request msg encoded'
    s.sendall(tx_buf)
    print 'request msg sended'

    len_buf = MAX_TCP_SZ
    recv_cnt = 0
    bytes_cnt = 0
    len_data_total = 0
    fp = open('house.db', 'wb+')
    while True:
        rx_buf = s.recv(MAX_BUF_SZ)
        len_buf = len(rx_buf)
        if 0 == len_buf:
            break
        print 'response msg received: %d bytes' % len_buf
        if 0 == recv_cnt:
            cmd_resp, len_data_total = struct.unpack('<II', rx_buf[0:8])
            len_data = len_buf - 8
            print 'response msg decoded, cmd = 0x%x, len_data_total = %d, len_data = %d' % (cmd_resp, len_data_total, len_data)
            data_base = buffer(rx_buf, 8, len_data)
            fp.write(data_base)
        else:
            len_data = len_buf
            data_base = buffer(rx_buf, 0, len_data)
            fp.write(data_base)
        recv_cnt = recv_cnt +1
        bytes_cnt = bytes_cnt + len_data
    if bytes_cnt == len_data_total:
        print '%d bytes received from server' % bytes_cnt
    else:
        print 'recv contents corrupted, abort'
    fp.close()
    os.system('rm -f house.sqlite;sqlite3 house.db .dump | iconv -f gb18030 -t utf-8 | sqlite3 house.sqlite')


def single_ctrl_query(room_id, dev_id):
    if not LOG_ON:
        logon_server()
    s = connect_server()
    tx_buf = struct.pack('<IIBBBB', CMD_SINGLE_CTRL_REQ, 0x04, OP_MODE_QUERY, room_id, dev_id, 0x0)
    s.sendall(tx_buf)
    rx_buf = s.recv(MAX_BUF_SZ)
    print 'dev query resp len = %d' % len(rx_buf)
    cmd_resp, len_data, op_mode_rsp, dev_id2, op_code_rsp, no_use = struct.unpack('<IIBBBB', rx_buf)
    print 'dev query result : cmd_resp = 0x%x, len_data = %d, op_mode_rsp = %d, dev_id2 = %d, op_code_rsp = 0x%x' % (cmd_resp, len_data, op_mode_rsp, dev_id2, op_code_rsp)
    disconnect_server(s)
    assert cmd_resp == CMD_SINGLE_CTRL_RSP and len_data == 0x04 and op_mode_rsp == OP_MODE_QUERY and dev_id2 == dev_id
    return op_code_rsp

def single_ctrl(op_mode, room_id, dev_id, op_code_req):
    if not LOG_ON:
        logon_server()
    s = connect_server()
    tx_buf = struct.pack('<IIBBBB', CMD_SINGLE_CTRL_REQ, 0x04, op_mode, room_id, dev_id, op_code_req)
    s.sendall(tx_buf)
    if OP_MODE_ZIG == op_mode:
        rx_buf = s.recv(MAX_BUF_SZ)
        print 'single ctrl resp len = %d' % len(rx_buf)
        cmd_resp, len_data, op_mode_rsp, dev_id2, op_code_rsp, no_use = struct.unpack('<IIBBBB', rx_buf)
        print 'single ctrl result : cmd_resp = 0x%x, len_data = %d, op_mode_rsp = %d, dev_id2 = %d, op_code_rsp = 0x%x' % (cmd_resp, len_data, op_mode_rsp, dev_id2, op_code_rsp)
        assert cmd_resp == CMD_SINGLE_CTRL_RSP and len_data == 0x04 and op_mode_rsp == OP_MODE_QUERY and dev_id2 == dev_id
        ret = op_code_rsp
    else:
        ret = 0
    disconnect_server(s)
    return ret

def get_app_info(room_name, dev_name):
    if not HAS_DB():
        get_house_db()
    db_conn = sqlite3.connect('house.sqlite')
    c = db_conn.cursor()
    for row in c.execute('select * from roominfo'):
        if -1 != row[2].find(room_name):
            room_id = row[0]
            break
    for row in c.execute('select * from roomDevice where room_id = %d' % room_id):
        if -1 != row[1].find(dev_name):
            dev_id = row[0]
            app_id = row[5]
            mod_id = row[4]
    db_conn.close()
    print 'room_id %d, dev_id %d, app_id %s, mod_id %s' % (room_id, dev_id, app_id, mod_id)
    return room_id, dev_id, app_id, mod_id

def operate_single(room, dev, op_name):
    room_id, dev_id, app_id, mod_id = get_app_info(room, dev)
    entry = tbl_app[app_id][mod_id]
    req_info = entry['req']
    try:
        rsp_info = entry['rsp']
        op_mode = OP_MODE_ZIG
        op_code_rsp = single_ctrl_query(room_id, dev_id)
        #如果不是可调灯这种反馈码不固定的家具，且查询返回码==想要的反馈码
        if not isinstance(rsp_info[op_name], list) and op_code_rsp == rsp_info[op_name]:
            print 'app has been in expected status, need no change'
            return True
    except KeyError:
        op_mode = OP_MODE_IR
        pass

    op_code_req = req_info[op_name]
    print 'input param : room_id = %d, dev_id = %d, value = 0x%x' % (room_id, dev_id, op_code_req)
    op_code_rsp = single_ctrl(op_mode, room_id, dev_id, op_code_req) 
    if op_mode == OP_MODE_ZIG and not (op_code_rsp == rsp_info[op_name] or op_code_rsp in rsp_info[op_name]):
        print 'operate_single fail, return val = 0x%x' % op_code_rsp
        return False
    return True

