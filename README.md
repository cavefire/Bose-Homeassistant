# Bose Homeassistant

This is a custom component for Home Assistant to integrate with Bose soundbars / speakers.
The speakers are controlled 100% locally. However, a cloud account is needed and required configured in the integration. Read more about this in the [BOSE Account](#bose-account) section.

## Installation

### Using HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=Bose-Homeassistant&owner=cavefire)

1. Click the link above to open the integration in HACS.
2. Install the integration.

### Manual Installation

1. Clone or download this repository.
2. Copy the `custom_components/bose` directory to your Home Assistant `config` directory.
3. Restart Home Assistant.

## Setup

1. Go to "Configuration" -> "Devices & Services" -> "Add Device" -> "Bose".
2. Enter your BOSE account credentials (required, see [BOSE Account](#bose-account)).
3. Select the device you want to add (discovered by mDNS or manually).
4. Click "Add Device".

## BOSE Account

BOSE requires you to have an account in order to control a soundbar / speaker. Even if you allow access for all users in the network, you still need to provide your account credentials.

So this integration is making use of `pybose`'s authentication. You can find more information about this in the [pybose repository](https://github.com/cavefire/pybose).

`pybose` is a Python library that reverse-engineers the BOSE API. It is used to authenticate with the BOSE API and to control the soundbar / speaker. After the initial call to the BOSE API, an access token is stored, making the following calls to the device locally.

## Features

This is the list of features implemented in the integration. Non-marked features are not yet implemented. Feel free to do so!

- [x] Control volume
- [x] See current volume
- [x] See currently playing media (image and title)
- [ ] Control power
- [x] Control media (play, pause, next, previous)
- [x] Switch to TV source
- [x] Switch to aux sources
- [ ] Control bluetooth 
- [x] Audio setup (bass, treble, ...)
- [x] Configure bass module / surround speakers
- [ ] Group speakers
- [ ] HDMI settings
- [ ] Standby timer settings
- [ ] Optical activation settings
- [x] Battery Level (for portable speakers)
- [x] Send arbitrary request via service

### Services

- `bose.send_custom_request` - Send a custom request to the speaker. This can be used to control features that are not yet implemented in the integration and for debugging purposes.

### Supported Devices

All devices controllable using the BOSE App should work. Here is the list of devices, that have been tested:

**Soundbars:**
- [x] Soundbar 500
- [x] Soundbar 700
- [x] Soundbar 900
- [x] Soundbar Ultra

**Home Speakers:**
- [x] Home Speaker 300
- [x] Home Speaker 500

**Others:**
- [x] Music Amplifier
- [x] Portable Speaker

If you have a device that is not listed here, please open an issue or a pull request.
These devices only work with the features that are marked as completed above. Some features might not work due to hardware or software limitations. 
**If a feature is missing on your device, please open an issue.**

## Contributing
This project is a work in progress, and contributions are welcome!
If you encounter issues, have feature requests, or want to contribute, feel free to submit a pull request or open an issue.

My goal is to split the integration from the `pybose` library, so that it can be used in other projects as well. So every function that is calling the speaker's websocket, should be implemented in the `pybose` library. The integration should only be responsible for the Home Assistant part.

## Disclaimer
This project is not affiliated with Bose Corporation. The API is reverse-engineered and may break at any time. Use at your own risk.

**To the BOSE legal team:**

All API keys used in this project are publicly available on the Bose website.

There was no need to be a computer specialist to find them, so: Please do not sue me for making people use their products in a way they want to.

If you have any issues with me publishing this, please contact me! I am happy to discuss this with you and make your products better.

## License
This project is licensed under GNU GPLv3 - see the [LICENSE](LICENSE) file for details.
