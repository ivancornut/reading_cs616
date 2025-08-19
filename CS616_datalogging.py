from counter import PWMCounter
from machine import Pin, PWM, Timer,I2C,lightsleep,WDT, idle, ADC
from time import ticks_ms, ticks_diff, sleep, ticks_us
import json
import urtc
import sdcard
import vfs
import os
import CD4051

class logger():
    ''' datalogger class that allows to save data
        should soon be in its own class and module '''
    
    def __init__(self,column_names = ["var1","var2","var3","var4"],rtc_clock=None):
        # initialising the SD card for the Pi Cowbell datalogger
        cs = Pin(17,Pin.OUT)
        spi = machine.SPI(0, baudrate=1000000,polarity=0,phase=0,bits=8,firstbit=machine.SPI.MSB,sck=Pin(18),mosi=Pin(19),miso=Pin(16))
        self.sd = sdcard.SDCard(spi, cs)
        self.filsys = vfs.VfsFat(self.sd)
        vfs.mount(self.filsys, "/sd") # mount the SD card
        
        self.var_names = column_names # names of the columns in csv files
        self.rtc = rtc_clock
        
        self.battery_pin = ADC(28)
        self.voltage_drop_factor = 1/(21.47/(66.1+21.47))
        try:
            os.stat('info.json') # file exists and can be found
            with open('info.json','r') as f:
                config = json.load(f)
            self.file_prefix = config["device_name"]
            self.timestep = int(config["timestep"])
        except:
            self.file_prefix = "data"
    
    def read_battery_voltage(self):
        sensor_value = 0
        for i in range(0,10):
            sensor_value = sensor_value + self.battery_pin.read_u16()/10
        self.battery_voltage = sensor_value * (3.3 / 65535) * self.voltage_drop_factor

    def agm_battery_soc(self):
        if self.battery_voltage >= 12.7:
            self.battery_SOC = 100.0
        elif self.battery_voltage >= 12.4:
            self.battery_SOC = 75 + 25 * (self.battery_voltage - 12.4) / 0.3
        elif self.battery_voltage >= 12.2:
            self.battery_SOC = 50 + 25 * (self.battery_voltage - 12.2) / 0.2
        elif self.battery_voltage >= 12.0:
            self.battery_SOC = 25 + 25 * (self.battery_voltage - 12.0) / 0.2
        elif self.battery_voltage >= 11.8:
            self.battery_SOC = 10 + 15 * (self.battery_voltage - 11.8) / 0.2
        else:
            self.battery_SOC = 0.0

    def save_data(self,data=[0,9,99,999]):
        now = self.rtc.datetime() # check date
        # the device creates a new file every day this is easier to handle. 
        self.filename = "/sd/"+self.file_prefix+'_'+str(now.year)+"-"+str(now.month)+"-"+str(now.day)+".csv"
        # check if file exists and if doesn't create first line with column names
        try:
            os.stat(self.filename) # file exists and can be found
        except:
            with open(self.filename,'a') as f:
                # write the header
                f.write("DateTime,Battery_voltage,Battery_SOC")
                for name in self.var_names:
                    f.write(",")
                    f.write(name)
                f.write("\n")
        
        with open(self.filename,'a') as f:
            # write the data
            now = self.rtc.datetime()
            self.read_battery_voltage()
            self.agm_battery_soc()
            f.write(f"{now.year:04d}-{now.month:02d}-{now.day:02d}T{now.hour:02d}:{now.minute:02d}:{now.second:02d}")
            f.write(f",{self.battery_voltage:.3f},{self.battery_SOC:.3f}")
            for n,val in enumerate(data):
                f.write(",")
                f.write("%1.4f" % val)
            f.write("\n")
            print('Done with writing_to_file')
            
class datalogger_cs616:
    
    def __init__(self,meas_pin = 13,timestep=15,number_cs616=8,CS616=True,test=True): 
        #self.enable_Pins_addr = [6,7,8,9,10,11,12,13] # the GPIO of pins for enabling CS616
        self.timestep = timestep
        self.number = number_cs616
        self.proto = test
        
        self.enable_Pin = Pin(14,Pin.OUT) # Pin to enable sensors with 5V
        self.enable_Pin.value(0)
        
        self.enable_control = CD4051.CD4051(7,8,9) # control of the first CD4051 switch
        self.signal_control = CD4051.CD4051(10,11,12) # control of the second CD4051 switch
        
        if not self.proto:
            # intitialise i2C for urtc clock on Pi Cowbell datalogger shield
            self.i2c_clock = I2C(0,scl=Pin(5), sda=Pin(4))
            self.rtc = urtc.PCF8523(self.i2c_clock)
            
            # create the column names for each sensor
            col_names = []
            for i in range(0,number_cs616):
                col_names.append("TDR"+str(i)+"_us")
                col_names.append("TDR"+str(i)+"_WC%")
            self.Logging = logger(col_names,self.rtc)
            self.timestep = self.Logging.timestep
        
        # handle the frequency counting Pin 
        self.pin_counter = PWMCounter(meas_pin, PWMCounter.EDGE_RISING)
        self.pin_counter.set_div() # Set divisor to 1 (just in case)
        self.pin_counter.start() # Start counter
        self.pin_counter.stop() # Stop counter
        
        ''' Set up the watchdog, the max timeout on pi pico
        is 8333ms. The watchdog reinits the device if it
        is stuck. Very useful for dataloggers. This also
        means that we need to wake device from sleep'''
        self.watchdog = WDT(timeout=8000)
        
        self.led = Pin(25, Pin.OUT) # internal led of the Pi Pico
        self.led.value(0)
    
    def _hello(self):
        for i in range(0,10):
            self.led.value(1)
            sleep(0.3)
            self.watchdog.feed()
            self.led.value(0)
            sleep(0.5)
    
    def _cs616_measure(self):
        ''' The frequency measuring function
        the period of the CS616 is then used to deduce soil
        water content'''
        sampling_time = 100000
        mean_freq = 0
        for i in range(1,11):
            self.pin_counter.stop()
            self.pin_counter.reset()
            cond = True
            last_check = ticks_us()
            self.pin_counter.start()
            
            while cond:
                if ticks_diff(tmp := ticks_us(), last_check) >= sampling_time:
                    freq = self.pin_counter.read_and_reset() / (sampling_time / 1000000)
                    mean_freq = mean_freq + (freq)/10
                    cond = False
        period = 1/mean_freq * 1000000 # in us
        print(period,mean_freq)
        return period
    
    def _convert_period_to_wc(self,period_value):
        # this function is given in the manual of the CS616
        VW=(-0.0663 + (-0.0063*period_value)+(0.0007*period_value**2))*100
        return VW
    
    def _meas_sequence(self):
        self.data_values = []
        self.enable_Pin.value(1)
        for i in range(0,self.number):
            print(i)
            self.enable_control.set_output(i)
            self.signal_control.set_output(i)
            sleep(2) # just wait for it to turn on
            if not self.proto:
                try:
                    value_1 = self._cs616_measure() # Measure frequency
                    value_2 = self._convert_period_to_wc(value_1) # convert freq to water content

                except:
                    value_1 = 999.9
                    value_2 = 999.9
            else:  
                try:
                    value_1 = self._cs616_measure() # Measure frequency
                    value_2 = self._convert_period_to_wc(value_1) # convert freq to water content
                    print("Values:",value_1, value_2)
                except:
                    value_1 = 999.9
                    value_2 = 999.9
            
            self.data_values.append(value_1)
            self.data_values.append(value_2)
            self.watchdog.feed()
            self.led.value(1)
            sleep(0.1)
            self.led.value(0)
        self.enable_Pin.value(0)
    
    def run(self):
        self._hello()
        while True:
            if self.proto:
                print("This is prototyping")
                self._meas_sequence()
                self.watchdog.feed()
                sleep(2)
            else:
                now = self.rtc.datetime()
                if (now.minute%self.timestep) == 0:
                    self._meas_sequence()
                    self.Logging.save_data(self.data_values)
                    print("Done saving data")
                    self.watchdog.feed()
                    for i in range(0,30):
                        lightsleep(5750)
                        self.watchdog.feed()
                        self.led.value(1)
                        sleep(0.05)
                        self.led.value(0)
                lightsleep(5750)
                self.watchdog.feed()
                self.led.value(1)
                sleep(0.05)
                self.led.value(0)
            #idle()

sleep(5) # just some time so usb can connect before the program is launched
Datalogger = datalogger_cs616(meas_pin=13,timestep=2,number_cs616=8,CS616=True,test=False)
Datalogger.run()