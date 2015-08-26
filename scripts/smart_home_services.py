#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Copyright (C) 2013-2015 Runji
#
import sys
import roslib
import rospy
from qbo_smart_home_services.srv import *
from house_ctrl import *

def handle_set_host(req):
    global HOST
    HOST = req.ip
    return SetHostResponse(True)

def handle_single_ctrl(req):
    room_name, dev_name, op_name = req.room_name.decode('utf-8'), req.dev_name.decode('utf-8'), req.op_name.decode('utf-8')
    print "======: room %s, dev %s, op %s" % \
        (room_name, dev_name, op_name)

    ret = operate_single(room_name, dev_name, op_name)
    return SingleCtrlResponse(ret)

if __name__ == "__main__":
    rospy.init_node('SmartHomeService')

    #init host ip update service
    s0 = rospy.Service('/smart_home_set_host', SetHost, handle_set_host)

    #init single ctrl service
    init_appliance_tbl(tbl_app)
    s1 = rospy.Service('/smart_home_single_ctrl', SingleCtrl, handle_single_ctrl)

    rospy.spin()

