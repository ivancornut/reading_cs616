# Frequency measurement example using PWMCounter.
# It measures frequency generated on GP0
# with counter configured on GP15.

from machine import Pin, PWM, Timer
from time import ticks_ms, ticks_diff, sleep, ticks_us
from machine import mem32

class PWMCounter:
    LEVEL_HIGH = 1
    EDGE_RISING = 2
    EDGE_FALLING = 3
    
    def __init__(self, pin, condition = LEVEL_HIGH):
        assert pin < 30 and pin % 2, "Invalid pin number"
        slice_offset = (pin % 16) // 2 * 20
        self._pin_reg = 0x40014000 | (0x04 + pin * 8)
        self._csr = 0x40050000 | (0x00 + slice_offset)
        self._ctr = 0x40050000 | (0x08 + slice_offset)
        self._div = 0x40050000 | (0x04 + slice_offset)
        self._condition = condition
        self.setup()
    
    def setup(self):
        # Set pin to PWM
        mem32[self._pin_reg] = 4
        # Setup PWM counter for selected pin to chosen counter mode
        mem32[self._csr] = self._condition << 4
        self.reset()
    
    def start(self):
        mem32[self._csr + 0x2000] = 1
        
    def stop(self):
        mem32[self._csr + 0x3000] = 1
    
    def reset(self):
        mem32[self._ctr] = 0
    
    def read(self):
        return mem32[self._ctr]
    
    def read_and_reset(self):
        tmp = self.read()
        self.reset()
        return tmp
    
    def set_div(self, int_ = 1, frac = 0):
        if int_ == 256: int_ = 0
        mem32[self._div] = (int_ & 0xff) << 4 | frac & 0xf


# Set PWM to output test signal
pwm = PWM(Pin(4))
pwm.duty_u16(1 << 15)
pwm.freq(39000)

timer_read=Timer() # objet Timer pour appeler la boucle variation PWM
# Configure counter to count rising edges on GP15
counter = PWMCounter(13, PWMCounter.EDGE_RISING)
# Set divisor to 1 (just in case)
counter.set_div()
# Start counter
counter.start()

def freq_measure(timer_read):
    sampling_time = 100000
    
    global counter
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
    else:
        period = 1/mean_freq * 1000000 # in us
        VW=(-0.0663 + (-0.0063*period)+(0.0007*period**2))*100
        print(f"Frequency: {mean_freq:.2f}kHz")
        print(f"Period: {period:.2f}µs")
        print(f"Soil Moisture: {VW:.2f}%")
        print("---------------------------")
    #print(freq, period, VW)
p0 = Pin(0, Pin.OUT)
p0.value(1)
timer_read.init(period = 3000, callback = freq_measure)

#for i in range(1,10):
#    freq_measure()
#    sleep(2)

