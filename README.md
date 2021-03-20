# [https://github.com/Yonsm/ZhiViomi](https://github.com/Yonsm/ZhiViomi)

VoiMi Washer Component for HomeAssistant

云米洗衣机组件。目前仅验证了 WD10SA 型号可用，如果其它型号需要支持请给我[提 issue](https://github.com/Yonsm/ZhiViomi/issues)。

## 1. 安装准备

把 `zhiviomi` 放入 `custom_components`；也支持在 [HACS](https://hacs.xyz/) 中添加自定义库的方式安装。

_依赖 [ZhiMi](https://github.com/rytilahti/ZhiMi)，请一并安装。_
_依赖 [python-miio](https://github.com/rytilahti/python-miio)，运行时自动检查安装。_

## 2. 配置方法

参见 [我的 Home Assistant 配置](https://github.com/Yonsm/.homeassistant) 中 [configuration.yaml](https://github.com/Yonsm/.homeassistant/blob/main/configuration.yaml)

```
fan:
  - platform: zhiviomi
    name: 洗衣机
    host: Washer
    token: !secret washer_token
    did: 12345678
```

- `name` 配置必选。
- 设备配置
  - 只配置 `host` 和 `token` 为本地网络模式（经常超时）；
  - 只配置 `did` 为云端模式（无法洗烘和预约）；
  - 都配置则为混合模式（云端更新优先、本地动作优先）。建议使用此模式，既能避免超时问题，又能使用洗烘和预约模式。

_如何获取 `token` 和 `did`？_ 参见 [MiService](https://github.com/Yonsm/MiService)

## 3. 使用方式

![PREVIEW](https://github.com/Yonsm/ZhiViomi/blob/main/PREVIEW.png)

如图，其中 `清理` 表示切换 `烘干模式`；`定位` 表示切换 `预约`，默认时间为 `8` 点钟完成。如需修改请直接改 [vacuum.py](https://github.com/Yonsm/ZhiViomi/blob/main/custom_components/zhiviomi/vacuum.py) 中的 `DEFAULT_APPOINT_TIME = -8`，如 `-8` 表示 8 点钟，`8` 表示 8 小时后。

还可以使用 `vacuum.send_command` 批量调用命令，如 `turn_on;program=4;dry_mode=1;appoint=-8`。支持的命令有：

```
program|water_temp|spin_level|DryMode|appoint_time=<value>
turn_on|turn_off|start|pause|stop|clean_spot|locate|return_to_base
fanspeed=$黄金洗
dry_mode[=<1|0>]
appoint[=<-clock|hour>]
```

其中负数 `appoint` 为几点钟完成，正数为几小时候后完成。可参考 [我的洗衣机自动化](https://github.com/Yonsm/.homeassistant/blob/main/automations/washer.yaml)，一键预约洗衣、烘衣，充分利用峰谷电，每天早上 8 点洗烘完成。

## 4. 参考

- [ZhiDash](https://github.com/Yonsm/ZhiDash)
- [Yonsm.NET](https://yonsm.github.io)
- [Hassbian.com](https://bbs.hassbian.com/thread-12335-1-1.html)
- [Yonsm's .homeassistant](https://github.com/Yonsm/.homeassistant)
