#!/usr/bin/env python
#
# GrovePi Python library
# v1.2.2
#
# This file provides the basic functions for using the GrovePi
#
# The GrovePi connects the Raspberry Pi and Grove sensors.  You can learn more about GrovePi here:  http://www.dexterindustries.com/GrovePi
#
# Have a question about this example?  Ask on the forums here:  http://forum.dexterindustries.com/c/grovepi
#
'''
## License

The MIT License (MIT)

GrovePi for the Raspberry Pi: an open source platform for connecting Grove Sensors to the Raspberry Pi.
Copyright (C) 2017  Dexter Industries

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
# Initial Date: 13 Feb 2014
# Last Updated: 11 Nov 2016
# http://www.dexterindustries.com/
# Author	Date      		Comments
# Karan		13 Feb 2014  	Initial Authoring
# 			11 Nov 2016		I2C retries added for faster IO
#							DHT function updated to look for nan's

import sys
import time
import math
import struct
import numpy
from periphery import I2C, I2CError

debug = 0

if sys.version_info<(3,0):
	p_version = 2
else:
	p_version = 3

if sys.platform == 'uwp':
	bus_port = 1
else:
	import RPi.GPIO as GPIO
	rev = GPIO.RPI_REVISION
	if rev == 2 or rev == 3:
		bus_port = 1
	else:
		bus_port = 0

# I2C Address of Arduino
address = 0x04
i2c = I2C('/dev/i2c-' + str(bus_port))
max_recv_size = 10

# This allows us to be more specific about which commands contain unused bytes
unused = 0
retries = 10
additional_waiting = 0

# Get firmware version
version_cmd = [8]
# No data is available from the GrovePi
data_not_available_cmd = [23]

# Command Format
# digitalRead() command format header
dRead_cmd = [1]
# digitalWrite() command format header
dWrite_cmd = [2]
# analogRead() command format header
aRead_cmd = [3]
# analogWrite() command format header
aWrite_cmd = [4]
# pinMode() command format header
pMode_cmd = [5]
# Ultrasonic read
uRead_cmd = [7]
# Accelerometer (+/- 1.5g) read
acc_xyz_cmd = [20]
# RTC get time
rtc_getTime_cmd = [30]
# DHT Pro sensor temperature
dht_temp_cmd = [40]

# Grove LED Bar commands
# Initialise
ledBarInit_cmd = [50]
# Set orientation
ledBarOrient_cmd = [51]
# Set level
ledBarLevel_cmd = [52]
# Set single LED
ledBarSetOne_cmd = [53]
# Toggle single LED
ledBarToggleOne_cmd = [54]
# Set all LEDs
ledBarSet_cmd = [55]
# Get current state
ledBarGet_cmd = [56]

# Grove 4 Digit Display commands
# Initialise
fourDigitInit_cmd = [70]
# Set brightness, not visible until next cmd
fourDigitBrightness_cmd = [71]
# Set numeric value without leading zeros
fourDigitValue_cmd = [72]
# Set numeric value with leading zeros
fourDigitValueZeros_cmd = [73]
# Set individual digit
fourDigitIndividualDigit_cmd = [74]
# Set individual leds of a segment
fourDigitIndividualLeds_cmd = [75]
# Set left and right values with colon
fourDigitScore_cmd = [76]
# Analog read for n seconds
fourDigitAnalogRead_cmd = [77]
# Entire display on
fourDigitAllOn_cmd = [78]
# Entire display off
fourDigitAllOff_cmd = [79]

# Grove Chainable RGB LED commands
# Store color for later use
storeColor_cmd = [90]
# Initialise
chainableRgbLedInit_cmd = [91]
# Initialise and test with a simple color
chainableRgbLedTest_cmd = [92]
# Set one or more leds to the stored color by pattern
chainableRgbLedSetPattern_cmd = [93]
# set one or more leds to the stored color by modulo
chainableRgbLedSetModulo_cmd = [94]
# sets leds similar to a bar graph, reversible
chainableRgbLedSetLevel_cmd = [95]

# Read the button from IR sensor
ir_read_cmd=[21]
# Set pin for the IR receiver
ir_recv_pin_cmd=[22]
# Check if there's data coming from the IR receiver
ir_read_isdata=[24]

# Dust, Encoder & Flow Sensor commands
dust_sensor_read_cmd=[10]
dust_sensor_en_cmd=[14]
dust_sensor_dis_cmd=[15]
dust_sensor_int_cmd=[9]
dust_sensor_read_int_cmd=[6]
encoder_read_cmd=[11]
encoder_en_cmd=[16]
encoder_dis_cmd=[17]
flow_read_cmd=[12]
flow_disable_cmd=[13]
flow_en_cmd=[18]


# Function declarations of the various functions used for encoding and sending
# data from RPi to Arduino

# Write I2C block to the GrovePi

def write_i2c_block(address, block, custom_timing = None):
	for i in range(retries):
		try:
			msg = [I2C.Message(block)]
			i2c.transfer(address, msg)
			time.sleep(0.002 + additional_waiting)
			return
		except I2CError:
			time.sleep(0.003)

	raise IOError("GrovePi is unreachable")

# Read I2C block from the GrovePi
def read_i2c_block(address, no_bytes = max_recv_size):
	data = data_not_available_cmd
	count = 0

	while data[0] in [data_not_available_cmd[0], 255] and count < retries:
		try:
			read_bytes = [255] * no_bytes
			msg = [I2C.Message(read_bytes, read = True)]
			i2c.transfer(address, msg)
			data = msg[0].data

			time.sleep(0.002 + additional_waiting)
			if count > 0:
				count = 0

		except I2CError:
			count += 1
			time.sleep(0.003)

	if count == retries:
		raise IOError("GrovePi is unreachable in grovepi.read_i2c_block func")
	else:
		return data

def read_identified_i2c_block(address, read_command_id, no_bytes):
	data = [-1]
	while data[0] != read_command_id[0]:
		data = read_i2c_block(address, no_bytes + 1)

	return data[1:]

# Arduino Digital Read
def digitalRead(pin):
	write_i2c_block(address, dRead_cmd + [pin, unused, unused])
	data = read_identified_i2c_block(address, dRead_cmd, no_bytes = 1)[0]
	return data

# Arduino Digital Write
def digitalWrite(pin, value):
	write_i2c_block(address, dWrite_cmd + [pin, value, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Setting Up Pin mode on Arduino
def pinMode(pin, mode):
	if mode == "OUTPUT":
		write_i2c_block(address, pMode_cmd + [pin, 1, unused])
	elif mode == "INPUT":
		write_i2c_block(address, pMode_cmd + [pin, 0, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1


# Read analog value from Pin
def analogRead(pin):
	write_i2c_block(address, aRead_cmd + [pin, unused, unused])
	number = read_identified_i2c_block(address, aRead_cmd, no_bytes = 2)
	return number[0] * 256 + number[1]


# Write PWM
def analogWrite(pin, value):
	write_i2c_block(address, aWrite_cmd + [pin, value, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1


# Read temp in Celsius from Grove Temperature Sensor
def temp(pin, model = '1.0'):
	# each of the sensor revisions use different thermistors, each with their own B value constant
	if model == '1.2':
		bValue = 4250  # sensor v1.2 uses thermistor ??? (assuming NCP18WF104F03RC until SeeedStudio clarifies)
	elif model == '1.1':
		bValue = 4250  # sensor v1.1 uses thermistor NCP18WF104F03RC
	else:
		bValue = 3975  # sensor v1.0 uses thermistor TTC3A103*39H
	a = analogRead(pin)
	resistance = (float)(1023 - a) * 10000 / a
	t = (float)(1 / (math.log(resistance / 10000) / bValue + 1 / 298.15) - 273.15)
	return t


# Read value from Grove Ultrasonic
def ultrasonicRead(pin):
	write_i2c_block(address, uRead_cmd + [pin, unused, unused])
	number = read_identified_i2c_block(address, uRead_cmd, no_bytes = 2)
	return (number[0] * 256 + number[1])


# Read the firmware version
def version():
	write_i2c_block(address, version_cmd + [unused, unused, unused])
	number = read_identified_i2c_block(address, version_cmd, no_bytes = 3)
	return "%s.%s.%s" % (number[0], number[1], number[2])


# Read Grove Accelerometer (+/- 1.5g) XYZ value
# Need to investigate why this reports what was read with the previous command
# Doesn't look to be implemented on the GrovePi
def acc_xyz():
	write_i2c_block(address, acc_xyz_cmd + [unused, unused, unused])
	number = read_identified_i2c_block(address, acc_xyz_cmd, no_bytes = 3)
	if number[1] > 32:
		number[1] = - (number[1] - 224)
	if number[2] > 32:
		number[2] = - (number[2] - 224)
	if number[3] > 32:
		number[3] = - (number[3] - 224)
	return (number[0], number[1], number[2])


# Read from Grove RTC
# Doesn't look to be implemented on the GrovePi
def rtc_getTime():
	write_i2c_block(address, rtc_getTime_cmd + [unused, unused, unused])
	number = read_i2c_block(address)
	return number

# Read and return temperature and humidity from Grove DHT Pro
def dht(pin, module_type):
	write_i2c_block(address, dht_temp_cmd + [pin, module_type, unused])
	number = read_identified_i2c_block(address, dht_temp_cmd, no_bytes = 8)

	if p_version==2:
		h=''
		for element in (number[0:4]):
			h+=chr(element)

		t_val=struct.unpack('f', h)
		t = round(t_val[0], 2)

		h = ''
		for element in (number[4:8]):
			h+=chr(element)

		hum_val=struct.unpack('f',h)
		hum = round(hum_val[0], 2)
	else:
		t_val=bytearray(number[0:4])
		h_val=bytearray(number[4:8])
		t=round(struct.unpack('f',t_val)[0],2)
		hum=round(struct.unpack('f',h_val)[0],2)
	if t > -100.0 and t <150.0 and hum >= 0.0 and hum<=100.0:
		return [t, hum]
	else:
		return [float('nan'),float('nan')]

# after a list of numerical values is provided
# the function returns a list with the outlier(or extreme) values removed
# make the std_factor_threshold bigger so that filtering becomes less strict
# and make the std_factor_threshold smaller to get the opposite
def statisticalNoiseReduction(values, std_factor_threshold = 2):
	if len(values) == 0:
		return []

	mean = numpy.mean(values)
	standard_deviation = numpy.std(values)

	if standard_deviation == 0:
		return values

	filtered_values = [element for element in values if element > mean - std_factor_threshold * standard_deviation]
	filtered_values = [element for element in filtered_values if element < mean + std_factor_threshold * standard_deviation]

	return filtered_values


# Grove LED Bar - initialise
# orientation: (0 = red to green, 1 = green to red)
def ledBar_init(pin, orientation):
	write_i2c_block(address, ledBarInit_cmd + [pin, orientation, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove LED Bar - set orientation
# orientation: (0 = red to green,  1 = green to red)
def ledBar_orientation(pin, orientation):
	write_i2c_block(address, ledBarOrient_cmd + [pin, orientation, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove LED Bar - set level
# level: (0-10)
def ledBar_setLevel(pin, level):
	write_i2c_block(address, ledBarLevel_cmd + [pin, level, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove LED Bar - set single led
# led: which led (1-10)
# state: off or on (0-1)
def ledBar_setLed(pin, led, state):
	write_i2c_block(address, ledBarSetOne_cmd + [pin, led, state])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove LED Bar - toggle single led
# led: which led (1-10)
def ledBar_toggleLed(pin, led):
	write_i2c_block(address, ledBarToggleOne_cmd + [pin, led, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove LED Bar - set all leds
# state: (0-1023) or (0x00-0x3FF) or (0b0000000000-0b1111111111) or (int('0000000000',2)-int('1111111111',2))
def ledBar_setBits(pin, state):
	byte1 = state & 255
	byte2 = state >> 8
	write_i2c_block(address, ledBarSet_cmd + [pin, byte1, byte2])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove LED Bar - get current state
# state: (0-1023) a bit for each of the 10 LEDs
def ledBar_getBits(pin):
	write_i2c_block(address, ledBarGet_cmd + [pin, unused, unused])
	block = read_identified_i2c_block(address, ledBarGet_cmd, no_bytes = 2)
	return block[0] ^ (block[1] << 8)


# Grove 4 Digit Display - initialise
def fourDigit_init(pin):
	write_i2c_block(address, fourDigitInit_cmd + [pin, unused, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - set numeric value with or without leading zeros
# value: (0-65535) or (0000-FFFF)
def fourDigit_number(pin, value, leading_zero):
	# split the value into two bytes so we can render 0000-FFFF on the display
	byte1 = value & 255
	byte2 = value >> 8
	# separate commands to overcome current 4 bytes per command limitation
	if (leading_zero):
		write_i2c_block(address, fourDigitValue_cmd + [pin, byte1, byte2])
	else:
		write_i2c_block(address, fourDigitValueZeros_cmd + [pin, byte1, byte2])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - set brightness
# brightness: (0-7)
def fourDigit_brightness(pin, brightness):
	# not actually visible until next command is executed
	write_i2c_block(address, fourDigitBrightness_cmd + [pin, brightness, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - set individual segment (0-9,A-F)
# segment: (0-3)
# value: (0-15) or (0-F)
def fourDigit_digit(pin, segment, value):
	write_i2c_block(address, fourDigitIndividualDigit_cmd + [pin, segment, value])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - set 7 individual leds of a segment
# segment: (0-3)
# leds: (0-255) or (0-0xFF) one bit per led, segment 2 is special, 8th bit is the colon
def fourDigit_segment(pin, segment, leds):
	write_i2c_block(address, fourDigitIndividualLeds_cmd + [pin, segment, leds])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - set left and right values (0-99), with leading zeros and a colon
# left: (0-255) or (0-FF)
# right: (0-255) or (0-FF)
# colon will be lit
def fourDigit_score(pin, left, right):
	write_i2c_block(address, fourDigitScore_cmd + [pin, left, right])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - display analogRead value for n seconds, 4 samples per second
# analog: analog pin to read
# duration: analog read for this many seconds
def fourDigit_monitor(pin, analog, duration):
	write_i2c_block(address, fourDigitAnalogRead_cmd + [pin, analog, duration])
	read_i2c_block(address, no_bytes = 1)
	time.sleep(duration)
	return 1

# Grove 4 Digit Display - turn entire display on (88:88)
def fourDigit_on(pin):
	write_i2c_block(address, fourDigitAllOn_cmd + [pin, unused, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove 4 Digit Display - turn entire display off
def fourDigit_off(pin):
	write_i2c_block(address, fourDigitAllOff_cmd + [pin, unused, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove Chainable RGB LED - store a color for later use
# red: 0-255
# green: 0-255
# blue: 0-255
def storeColor(red, green, blue):
	write_i2c_block(address, storeColor_cmd + [red, green, blue])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove Chainable RGB LED - initialise
# numLeds: how many leds do you have in the chain
def chainableRgbLed_init(pin, numLeds):
	write_i2c_block(address, chainableRgbLedInit_cmd + [pin, numLeds, unused])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove Chainable RGB LED - initialise and test with a simple color
# numLeds: how many leds do you have in the chain
# testColor: (0-7) 3 bits in total - a bit for red, green and blue, eg. 0x04 == 0b100 (0bRGB) == rgb(255, 0, 0) == #FF0000 == red
#            ie. 0 black, 1 blue, 2 green, 3 cyan, 4 red, 5 magenta, 6 yellow, 7 white
def chainableRgbLed_test(pin, numLeds, testColor):
	write_i2c_block(address, chainableRgbLedTest_cmd + [pin, numLeds, testColor])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove Chainable RGB LED - set one or more leds to the stored color by pattern
# pattern: (0-3) 0 = this led only, 1 all leds except this led, 2 this led and all leds inwards, 3 this led and all leds outwards
# whichLed: index of led you wish to set counting outwards from the GrovePi, 0 = led closest to the GrovePi
def chainableRgbLed_pattern(pin, pattern, whichLed):
	write_i2c_block(address, chainableRgbLedSetPattern_cmd + [pin, pattern, whichLed])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove Chainable RGB LED - set one or more leds to the stored color by modulo
# offset: index of led you wish to start at, 0 = led closest to the GrovePi, counting outwards
# divisor: when 1 (default) sets stored color on all leds >= offset, when 2 sets every 2nd led >= offset and so on
def chainableRgbLed_modulo(pin, offset, divisor):
	write_i2c_block(address, chainableRgbLedSetModulo_cmd + [pin, offset, divisor])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove Chainable RGB LED - sets leds similar to a bar graph, reversible
# level: (0-10) the number of leds you wish to set to the stored color
# reversible (0-1) when 0 counting outwards from GrovePi, 0 = led closest to the GrovePi, otherwise counting inwards
def chainableRgbLed_setLevel(pin, level, reverse):
	write_i2c_block(address, chainableRgbLedSetLevel_cmd + [pin, level, reverse])
	read_i2c_block(address, no_bytes = 1)
	return 1

# Grove - Infrared Receiver - get the commands received from the Grove IR sensor
def ir_read_signal():
	write_i2c_block(address, ir_read_cmd + [unused, unused, unused])
	data_back = read_identified_i2c_block(address, ir_read_cmd, no_bytes = 7)

	return (data_back[0],
			data_back[1] + data_back[2] * 256,
			data_back[3] + data_back[4] * 256 + data_back[5] * (256 ** 2) + data_back[6] * (256 ** 3))

# Grove - Infrared Receiver - set the pin on which the Grove IR sensor is connected
def ir_recv_pin(pin):
	write_i2c_block(address, ir_recv_pin_cmd + [pin, unused, unused])
	read_i2c_block(address, no_bytes = 1)

# Grove - Infrared Receiver - check if there's any data that hasn't been read so far
def ir_is_data():
	write_i2c_block(address, ir_read_isdata + 3 * [unused])
	number = read_identified_i2c_block(address, ir_read_isdata, no_bytes = 1)

	return number[0] != 0

def dust_sensor_en(pin = 2):
	write_i2c_block(address, dust_sensor_en_cmd + [pin, unused, unused])
	read_i2c_block(address, no_bytes = 1)

def dust_sensor_dis():
	write_i2c_block(address, dust_sensor_dis_cmd + [unused, unused, unused])
	read_i2c_block(address, no_bytes = 1)

def dustSensorRead():
	"""
	By default, the sample rate is set to 1 at every 30 seconds and this
	function was written only for that interval.

	If you wish to use a different
	interval, then use dustSensorReadMore function. To set a
	different interval, use setDustSensrInterval function.
	"""
	write_i2c_block(address, dust_sensor_read_cmd + [unused, unused, unused])
	data_back = read_identified_i2c_block(address, dust_sensor_read_cmd, no_bytes = 4)[0:4]
	if data_back[0] != 255:
		lowpulseoccupancy=(data_back[3] * 65536 + data_back[2] * 256 + data_back[1])
		return [data_back[0], lowpulseoccupancy]
	else:
		return [-1,-1]

def setDustSensorInterval(interval_ms):
	byte1 = interval_ms & 0xFF
	byte2 = interval_ms >> 8
	write_i2c_block(address, dust_sensor_int_cmd + [byte1, byte2] + [unused])
	read_i2c_block(address, no_bytes = 1)

def getDustSensorInterval():
	write_i2c_block(address, dust_sensor_read_int_cmd + 3 * [unused])
	data_back = read_identified_i2c_block(address, dust_sensor_read_int_cmd, no_bytes = 2)[0:2]

	if -1 in data_back: return -1

	interval = data_back[0] + data_back[1] * 256
	return interval

def dustSensorReadMore(blocking = True):
	sampletime_ms = getDustSensorInterval()
	found, lpo = dustSensorRead()
	delay_to_reduce_traffic = 0.05
	while found in [0, -1] and blocking is True:
		if delay_to_reduce_traffic * 1000 < sampletime_ms:
			time.sleep(delay_to_reduce_traffic)
		found, lpo = dustSensorRead()

	if found in [0, -1] and blocking is False:
		return (-1, -1, -1)

	percentage = lpo * 100.0 / sampletime_ms
	concetration = 1.1 * percentage ** 3 - 3.8 * percentage ** 2 + 520 * percentage + 0.62

	return (lpo, percentage, concetration)

def encoder_en():
	write_i2c_block(address, encoder_en_cmd + [unused, unused, unused])
	read_i2c_block(address, no_bytes = 1)

def encoder_dis():
	write_i2c_block(address, encoder_dis_cmd + [unused, unused, unused])
	read_i2c_block(address, no_bytes = 1)

def encoderRead():
	write_i2c_block(address, encoder_read_cmd + [unused, unused, unused])
	read_identified_i2c_block(address, encoder_read_cmd, no_bytes = 2)[0:2]
	if data_back[0]!=255:
		return [data_back[0],data_back[1]]
	else:
		return [-1,-1]

def flowDisable():
	write_i2c_block(address, flow_disable_cmd + [unused, unused, unused])
	read_i2c_block(address, no_bytes = 1)

def flowEnable(pin = 2):
	write_i2c_block(address, flow_en_cmd + [pin, unused, unused])
	read_i2c_block(address, no_bytes = 1)

def flowRead():
	write_i2c_block(address, flow_read_cmd + [unused, unused, unused])
	data_back = read_i2c_block(address, no_bytes = 3)[0:3]
	#print data_back
	if data_back[0]!=255:
		return [data_back[0],data_back[2] * 256 + data_back[1]]
	else:
		return [-1,-1]
