from counter import PWMCounter
from machine import Pin, PWM, Timer
from time import ticks_ms, ticks_diff, sleep, ticks_us

testing = False
testing_pin = 4 # GPIO address of testing pin
frequency_counting_pin = 7 # GPIO address of frequency counter

number_cs616 = 2 # number of CS616 attached to pico

enable_Pins_addr = [0,1,2,3,5,6,7,8,9,10,11,12] # the GPIO of pins for enabling CS616

if testing:
    # this is to test that the frequency counter pin is working
    # In this case connect the testing pin to the frequency counting pin
    pwm = PWM(Pin(testing_pin))
    pwm.duty_u16(1 << 15) # we shift 1 bit 15 which is equivalent to u16/2
    pwm.freq(39000)

enable_pins = []
period_sensor = []
VW_sensor = []

for i in range(0,number_cs616):
    try:
        enable_pins.append(Pin(enable_Pins_addr[i], Pin.OUT)) # create list with all pins as output
        enable_pins[i].value(0) # set all outputs to zero
    except:
        print("Issue setting Pin "+str(enable_Pins_addr[i]))
    period_sensor.append(9999)
    VW_sensor.append(9999)
        
def freq_measure(counter):
    sampling_time = 100000
    #global counter
    mean_freq = 0
    for i in range(1,11):
        counter.stop()
        counter.reset()
        cond = True
        last_check = ticks_us()
        counter.start()
        while cond:
            if ticks_diff(tmp := ticks_us(), last_check) >= sampling_time:
                freq = counter.read_and_reset() / (sampling_time / 1000000)
                mean_freq = mean_freq + (freq)/10
                cond = False
    if mean_freq == 0:
        print("error no frequency")
        print("---------------------------")
        period = 9999.9
        VW = 9999.9
    else:
        period = 1/mean_freq * 1000000 # in us
        VW=(-0.0663 + (-0.0063*period)+(0.0007*period**2))*100
        print(f"Frequency: {mean_freq:.2f}kHz")
        print(f"Period: {period:.2f}µs")
        print(f"Soil Moisture: {VW:.2f}%")
        print("---------------------------")
        #print(freq, period, VW)
    counter.stop()
    return period, VW

counter_freq = PWMCounter(frequency_counting_pin, PWMCounter.EDGE_RISING)
counter_freq.set_div() # Set divisor to 1 (just in case)
counter_freq.start() # Start counter

while True:
    print("yes")
    u = 0
    for i in enable_pins: # we iterate over all the CS616 sensors
        i.value(1)
        sleep(2+)
        try:
            period_sensor[u], VW_sensor[u] = freq_measure(counter_freq)
        except:
            #in case of issue
            period_sensor[u] = 9999.9 
            VW_sensor[u] = 9999.9
            print("Problem with frequency measurement")
        
        sleep(5)
        i.value(0)
        u = u+1
    sleep(1)

    

