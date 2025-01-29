# Bose Homeassistant

This is a custom component for Home Assistant to integrate with Bose soundbars / speakers.
The speakers are controlled 100% locally. However, a cloud account is needed and required configured in the integration. Read more about this in the [BOSE Account](#bose-account) section.

**This integration is currently in development and is not yet ready for use.**

## Installation

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

- [x] Control volume
- [x] See current volume
- [x] See currently playing media (image and title)
- [ ] Control power
- [ ] Control media (play, pause, next, previous)
- [ ] Control source (TV / Bluetooth / ...)
- [ ] Audio setup (bass, treble, ...)
- [ ] Configure bass module / surround speakers
- [ ] Group speakers
- [ ] HDMI settings
- [ ] Standby timer settings
- [ ] Optical activation settings

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