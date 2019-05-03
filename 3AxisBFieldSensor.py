#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu May  2 11:52:34 2019

@author: maximilian
"""

import numpy as np
import time
from threading import Thread
from traits.api import HasTraits, Range, File, Float, Enum, Array, Instance, Int, String, Bool, Button, List, Tuple, Dict, Directory, HTML
from traitsui.api import spring,Handler, Tabbed, View, Item, VGroup, HGroup, HSplit,CodeEditor, HTMLEditor, RangeEditor, ButtonEditor, ListStrEditor, InstanceEditor
from chaco.api import GridContainer,ArrayPlotData, ArrayDataSource, add_default_grids, PlotAxis, Legend, OverlayPlotContainer, LinearMapper, Plot, jet,LinePlot, DataRange1D
from chaco.tools.api import LineSegmentTool, PanTool, ZoomTool, BroadcasterTool, LegendTool, LegendHighlighter
from chaco.scales.api import CalendarScaleSystem, TimeScale,TimeFormatter
from chaco.scales_tick_generator import ScalesTickGenerator
from chaco.chaco_plot_editor import ChacoPlotItem
from enable.api import ComponentEditor, Component

###serial libraries
import serial

import struct

class LinePlotClass(HasTraits):
    plot = Instance(Component)
    time_ds = Instance(ArrayDataSource)
    value_ds = Instance(ArrayDataSource)
    current_val = Float()
#    name = String()
    
    
    traits_view = View(HGroup(Item('current_val',style='readonly',label='value'),Item('plot', editor=ComponentEditor(), show_label=False),show_border=False), title="Chaco Plot")
    
    def create_container(self):
        
        container = OverlayPlotContainer(padding = 50, fill_padding = False,
                                     bgcolor = "lightgray", use_backbuffer=True)
        
        plots = {}
        #broadcaster = BroadcasterTool()
        
        indexmapper = LinearMapper(range=DataRange1D(self.time_ds))

        valuemapper = LinearMapper(range=DataRange1D(self.value_ds))
                
        plot = LinePlot(index=self.time_ds, value=self.value_ds,
                    index_mapper = indexmapper,
                    value_mapper = valuemapper,
                    orientation = "h",
                    color = "red",
                    bgcolor = "white",
                    line_width = 1.0,
                    line_style = "solid",
                    border_visible=True)
            
            
        plot.index.sort_order = "ascending"
        add_default_grids(plot)
                #add_default_axes(plot)
        
    
        container.add(plot)
        plots[0] = plot
        
        plot.tools.append(PanTool(plot, drag_button='left'))
        self.zoom = ZoomTool(plot)
        plot.overlays.append(self.zoom) 
        
        y_axis = PlotAxis(plots[0], orientation="left", title="B-Field")
        plots[0].underlays.append(y_axis)
        
        t_axis = PlotAxis(plots[0], orientation="bottom",# mapper=xmapper,
                    tick_generator=ScalesTickGenerator(scale=TimeScale(seconds=10),formatter=TimeFormatter()), title="Time")
        plots[0].underlays.append(t_axis)
        
       
        
        return container
        
    
    def _plot_default(self):      
        
        self.time_ds = ArrayDataSource([])
        self.value_ds = ArrayDataSource([])
        
        return self.create_container()        
        
        
    def update_plot(self, bfielddata, timedata):
        self.time_ds.set_data(timedata)
        self.value_ds.set_data(bfielddata)
        self.current_val = bfielddata[-1]

#        self.plot = self.create_container()
            
class AcqThread(Thread):
     axis = [b'X',b'Y',b'Z']
     
     def run(self):
        self.master.running = True
        start = time.time()
        counter = 0
        while not self.wants_abort:
             self.master.ser.reset_input_buffer()
             first = True
             while(first == True):
                  if self.master.ser.read() == self.axis[counter%3]:
                    if self.master.ser.read() == b'a':
                        if self.master.ser.read() == b'x':
                            first = False
                            threebytes = self.master.ser.read(3)
             #convert 3 bytes to int  
             val = struct.unpack('<i',threebytes+b'\x00')[0]
             self.master.data.data_arr[counter%3].append(val)
             counter = counter + 1
             if counter == 3:
                  self.master.data.index.append(time.time()-start)
                  counter = 0
             print('got data')
             time.sleep(1./self.master.sampling_rate)
             
        self.master.running = False
          
             
     
class Data(HasTraits):
     data_arr = Dict(value_trait = List)
     index = List()
     xplot=Instance(LinePlotClass)
     yplot=Instance(LinePlotClass)
     zplot =Instance(LinePlotClass)
     
     plots = []
     master = None
     
     traits_view = View(VGroup(HGroup(Item('xplot', editor=InstanceEditor(),style='custom',label="X:")),
                               HGroup(Item('yplot', editor=InstanceEditor(),style='custom',label="Y:")),
                               HGroup(Item('zplot', editor=InstanceEditor(),style='custom',label="Z:"))),resizable=True)
     
#     def __init__(self):
#          self.xplot = LinePlotClass()
     
     def __init__(self):
          self.data_arr[0] = []
          self.data_arr[1] = []
          self.data_arr[2] = []
          
          self.xplot = LinePlotClass()
          self.yplot = LinePlotClass()
          self.zplot = LinePlotClass()
          
          self.plots = [self.xplot, self.yplot, self.zplot]
     
     def _index_items_changed(self):
          offsets = [self.master.xoff,self.master.yoff,self.master.zoff]
          for i in range(3):
               bfielddata = (np.array(self.data_arr[i]) - offsets[i])*self.master.gauss_per_level
               self.plots[i].update_plot(bfielddata, np.array(self.index))
          print('updated data')
     
class OffThread(Thread):
     
     def run(self):
               self.master.off_running = True
               
               self.master.ser.write(b's')
               time.sleep(50/self.master.sampling_rate)
               set_i = len(self.master.data.index)-1
               time.sleep(50/self.master.sampling_rate)
               set_f = len(self.master.data.index)-1
               
               self.master.ser.write(b'r')
               time.sleep(50/self.master.sampling_rate)
               reset_i = len(self.master.data.index)-1
               time.sleep(50/self.master.sampling_rate)
               reset_f = len(self.master.data.index)-1
               
               offsets = []
               for i in range(3):
                    offsets.append(0.5*(np.mean(self.master.data.data_arr[i][set_i:set_f]) + np.mean(self.master.data.data_arr[i][reset_i:reset_f])))

               self.master.xoff = offsets[0]
               self.master.yoff = offsets[1]
               self.master.zoff = offsets[2]
               self.master.off_running = False
               
class PrecThread(Thread):
     
     def run(self):
               self.master.ser.reset_input_buffer()
               self.master.prec_running = True
               all_data = self.master.ser.read(self.master.sample_number)
               
               xvals = []
               yvals = []
               zvals = []
               vals = [xvals,yvals,zvals]
               end = len(all_data) - 1
               max_i = end - 18
               min_i = 0
               marker = ['Xax','Yax','Zax']
               while min_i < max_i:
                    for j in range(3):
                         index = all_data[min_i:].find(marker[j]) + min_i
                         val_bytes = all_data[index+3:index+6]
                         min_i = index + 6
                         
                         val_int = struct.unpack('<i',val_bytes+b'\x00')[0]
                         vals[j].append(val_int)
                   
               for i in range(3):
                    self.master.data.data_arr[i].extend(vals[i])
               indeces = list(np.linspace(0,1,num=len(xvals)))
               self.master.data.index.extend(indeces)
               
               #data analysis:
               self.master.x_pp = abs(max(xvals)-min(xvals))*self.master.gauss_per_level
               self.master.y_pp = abs(max(yvals)-min(yvals))*self.master.gauss_per_level
               self.master.z_pp = abs(max(zvals)-min(zvals))*self.master.gauss_per_level
               
               self.master.prec_running = False
               
class controller(HasTraits):
     address = String('/dev/ttyUSB1')
     baudrate = Int(128000)
     connect = Button()
     connected = Bool(False)
     
     gauss_per_level = Float(1)
     xoff = Float(0)
     yoff = Float(0)
     zoff = Float(0)
     find_off = Button("Find offsets")
     off_running = Bool(False)
     set_Btn = Button("Set Pulse")
     reset_Btn = Button("Reset Pulse")
     start_stop = Button('Start/Stop')
     running = Bool(False)
     sampling_rate = Float(25)
     
     #precision measurement (without resetting buffer)
     start_precision = Button('Start/Stop Precision Measurement')
     sample_number = Int(0)
     prec_running = Bool(False)
     x_pp = Float()
     y_pp = Float()
     z_pp = Float()
     
     #DATA Container
     data = Instance(Data)
     acquisition_thread = Instance(AcqThread)
     
     ser = None
     
     traits_view = View(HSplit(Item('data',editor=InstanceEditor(),style='custom',show_label=False,width=600),
                                             
                                    Tabbed(VGroup('address','baudrate', HGroup(Item('connect',show_label=False),Item('connected',style='readonly')),
                                                         'gauss_per_level', 
                                                         VGroup('xoff', 'yoff', 'zoff',Item('find_off',show_label=False)),label='settings'
                                             ),
                                             VGroup(Item('start_stop',show_label=False),
                                                         Item('sampling_rate',editor=RangeEditor(low=1,high=50,mode='slider')),Item('set_Btn',show_label=False),Item('reset_Btn',show_label=False),label='live measurement'),
                                             VGroup(Item('start_precision',show_label=False),'sample_number',Item('x_pp',style='readonly'),Item('y_pp',style='readonly'),Item('z_pp',style='readonly'),label='precision measurement')
                                             )),
                              
                              resizable=True,width=0.8
                       )
     
     def __init__(self):
          self.data = Data()
          self.data.master = self
#          self.data.xplot = LinePlotClass()
#          self.data.yplot = LinePlotClass()
#          self.data.zplot = LinePlotClass()
     
     
     def _connect_fired(self):
          try:
               self.ser = serial.Serial(self.address,baudrate=self.baudrate)
               self.connected = True
          except:
               print('connecting failed...')
               self.connected = False
               
     def _start_stop_fired(self):
          ##start thread
          if self.connected == True:
               if self.acquisition_thread and self.acquisition_thread.isAlive():
                 self.acquisition_thread.wants_abort=True
                 while(self.running == True):
                         pass
                 self.acquisition_thread = None
                 print "Stopped measuring!"
               else:
                 print "Started measuring!"
                 #delete old data
                 for i in range(3):
                      self.data.data_arr[i] = []
                 self.data.index = []
                 
                 #start thread
                 self.acquisition_thread=AcqThread()
                 self.acquisition_thread.wants_abort=False
                 self.acquisition_thread.master=self
                 
                 self.acquisition_thread.start()
          else:
               print('not connected')
          
          
          
     def _set_Btn_fired(self):
          self.ser.write(b's')
          
     def _reset_Btn_fired(self):
          self.ser.write(b'r')
          
     def _find_off_fired(self):
          if self.connected == True:
               if self.acquisition_thread and self.acquisition_thread.isAlive():
                    pass
               else:
                    self._start_stop_fired()
               
               if self.off_running == False and self.prec_running == False:
                    self.off_thread=OffThread()
                    self.off_thread.master=self
                    self.off_thread.start()
               else:
                    print('finding offset is running')
          else:
               print('not connected')
               
               
     def _start_precision_fired(self):
          if self.connected == True:
               if self.acquisition_thread and self.acquisition_thread.isAlive():
                    self.acquisition_thread.wants_abort=True
                    while(self.running == True):
                         pass
                    self.acquisition_thread = None
                    print("Stopped measuring!")
               #do measurement
               if self.sample_number > 0:
                    if self.off_running == False and self.prec_running == False:
                         for i in range(3):
                              self.data.data_arr[i] = []
                         self.data.index = []
                         
                         self.prec_thread=PrecThread()
                         self.prec_thread.master=self
                         self.prec_thread.start()
                    else:
                         print('something is running')
          else:
               print('not connected')
               
          
if __name__== '__main__':
    s=controller()
    s.configure_traits()