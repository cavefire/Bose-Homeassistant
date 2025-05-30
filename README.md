# Bose Homeassistant

This is a custom component for Home Assistant to integrate with Bose soundbars / speakers.
The speakers are controlled 100% locally. However, a cloud account is needed and required configured in the integration. Read more about this in the [BOSE Account](#bose-account) section.

![Preview](images/entities.jpg)

![Preview](images/media_player.jpg)

## Installation

### Using HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](http://mine.li/mTnn1)](http://mine.li/uuOUj)

1. Click the link above to open the integration in HACS.
2. Install the integration.

### Manual Installation

1. Clone or download this repository.
2. Copy the `custom_components` directory of this repository to your Home Assistant `config` directory.
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

- [x] Control power
- [x] Control volume
- [x] See current volume
- [x] See currently playing media (title, artist, album, cover, duration and position)
- [x] Control media (play, pause, next, previous)
- [x] Select sources (aux, chinch, optical - based on the speaker)
- [ ] Control bluetooth 
- [x] Audio setup (bass, treble, center, surround)
- [x] Enable / disable bass module and gain
- [x] Enable / disable surround speakers 
- [x] Group speakers
- [x] HDMI-CEC settings
- [x] Standby timer settings
- [x] Optical activation settings
- [x] Battery Level (for portable speakers)
- [x] Rebroadcast latency settings
- [x] Standby timer settings
- [x] Dialog settings (AI Dialog Mode, Dialog Mode, Normal - based on the speaker)
- [x] Dual Mono settings
- [x] Send arbitrary request via service

### Group speakers
You can group multiple Bose speakers together, like in the Bose App. This is done by using the service `media_player.join`.

**Target:** Select the entity you want to be the master speaker (max. 1 media player!)
**Group members:** Select the entities you want to join the master speaker.

You can either join all desired speakers together, or you can join them one by one.
Joining a speaker to a other speaker, that is already in a group, will join the new speaker to the existing group.

**Example:**
```yaml
action: media_player.join
data:
  group_members:
    - media_player.bose_smart_ultra_soundbar
target:
  entity_id: media_player.bose_music_amplifier
```

To remove a speaker from the group, use the service `media_player.unjoin`. If the target is the master speaker, the group will be dissolved. Otherwise the target will be removed from the group.

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

If you like this project, consider supporting me 
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png)](https://www.buymeacoffee.com/cavefire)


## Disclaimer
This project is not affiliated with Bose Corporation. The API is reverse-engineered and may break at any time. Use at your own risk.

**To the BOSE legal team:**

All API keys used in this project are publicly available on the Bose website.

There was no need to be a computer specialist to find them, so: Please do not sue me for making people use their products in a way they want to.

If you have any issues with me publishing this, please contact me! I am happy to discuss this with you and make your products better.

## License
This project is licensed under GNU GPLv3 - see the [LICENSE](LICENSE) file for details.
