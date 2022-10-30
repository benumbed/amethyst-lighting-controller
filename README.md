# Amethyst Lighting Controller

## Note on this Repo

This code isn't all that useful without the underlying custom hardware. I've made the code public so it can
serve as an example around using MicroPython on the Raspberry Pi Pico in more peripheral-heavy uses. There are no 
guarantees this code is efficient or even the best way to do things, it's just here as a potential educational resource.

Of interest might be [temperature.py](src/temperature.py), which contains an implementation of the Steinhart-Hart 
equations used for converting voltage across a thermistor to a temperature.

## Project Information

Below is some information about what things are attached to this controller, along with links to where I purchased the
items.

### Microcontroller

* RP2040 (by means of the Raspberry Pi Pico) (https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html)

### Peripherals

* ADS1115 (https://www.amazon.com/gp/product/B07VPFLSMX) -- Used for monitoring the temperature probes attached to the custom LED strips used in the build
* DHT20 (https://www.mouser.com/ProductDetail/SparkFun/SEN-18364) -- General environment monitoring on the controller board
* INA3221 (https://www.amazon.com/gp/product/B09PHLSJ2G) -- Monitoring current running through each LED string (144 RGBW LED/1m strips, potential to draw enough power to start fires)

### LEDs

The LEDs in use are [BTF-LIGHTING RGBW RGB+Natural White SK6812 (Similar WS2812B) Individually Addressable 3.3ft 1m 144(2X72)](https://www.amazon.com/gp/product/B01N0MA316).

The following diffusers were used to both sink heat and diffuse the light (shocking!).

* https://www.amazon.com/gp/product/B085VT59Q4
* https://www.amazon.com/gp/product/B07P8NWBP5

These strips have [neodymium magnets](https://www.mcmaster.com/catalog/128/3833) attached to them to allow them to be
attached securely to the case, while remaining removable for maintenance.

### Power Supply

**WARNING:** High-density LED lighting consumes a considerable amount of power, and as a result, careful planning is 
required when sizing all power supply components. In addition to the power components, care must also be exercised with 
heat management. High-density RGBW LED strips at full load can get hot enough to burn you and melt cabling if improperly 
cooled! Lack of care in these areas can cause personal injury or straight-up fires.

Ok now that the standard warning is out of the way, on to the details.

I use 2x 5V 15A buck converters connected to the main PSU 12V rail to power all the strips (and fan LEDs) in the system.
[BINZET DC Converter Step Down Regulator 5V Regulated Power Supplies Transformer Converter (5V 15A 75W)](https://www.amazon.com/gp/product/B08Q3LZBZH)
These converters do have basic protections built in, but because I prefer to be careful, each LED strip power feed is
protected by [5A 16V polyfuses](https://www.mouser.com/ProductDetail/Littelfuse/16R500GU). These also protect the 
INA3221 boards from seeing too much current in the event of a failure (the boards are not capable of handling
tremendous amounts of power per-channel).

The 12V side of the buck converters are protected by standard fast-blow fuses.

Cabling feeding the buck converters is pretty standard [18 AWG](https://mainframecustom.com/product-category/cable-sleeving/wire/18awg/) used for building custom PC power cabling. 
Side note, Mainframe Customs is a fantastic resource for custom PC power cabling supplies, my interactions with them 
were great!

The cabling in use from the current sensors to the strips is [AOTOINK 100ft Extension Cable 3 Pin Wire Cord 30M 22AWG Hookup Electrical 3 Color Wire](https://www.amazon.com/gp/product/B08JTZKN4M).
I would recommend using care with cabling like this and LED density like this project uses. Stranded core 22 AWG is 
sufficient for low current applications __only__.

In Amethyst's case, the runs are short and the airflow in the case is adequate to keep the insulation within 
temperature spec. The runs were also observed under full-load with a [thermal camera](https://www.amazon.com/HIKMICRO-Resolution-Measurement-4%C2%B0F-1022%C2%B0F-Temperature/dp/B09FTFHTPR) to ensure they stayed within the
insulation's safety envelope. However, in future builds I will most likely use solid-core 22 AWG (or larger) for the 
additional headroom it provides.

I used [wire ferrules](https://www.amazon.com/gp/product/B07PJK2VNT)
on the current-sensor end of the cabling. Yes, the ferrules are cheap and Amazon-sourced, however if crimped properly
they work just fine. The LED side of the cabling is soldered directly to the strips.