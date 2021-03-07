# [https://github.com/Yonsm/ZhiViomi](https://github.com/Yonsm/ZhiViomi)

VoiMi Washer Component for HomeAssistant

云米洗衣机组件。目前仅验证了 WD10SA 型号可用，如果其它型号需要支持请给我[提 issue](https://github.com/Yonsm/ZhiViomi/issues)。

## 1. 安装准备

把 `zhiviomi` 放入 `custom_components`；也支持在 [HACS](https://hacs.xyz/) 中添加自定义库的方式安装。

_依赖 [python-miio](https://github.com/rytilahti/python-miio)，运行时自动检查安装。_

## 2. 配置方法

参见 [我的 Home Assistant 配置](https://github.com/Yonsm/.homeassistant) 中 [configuration.yaml](https://github.com/Yonsm/.homeassistant/blob/main/configuration.yaml)

```
fan:
  - platform: zhiviomi
    name: 洗衣机
    host: Washer
    token: !secret washer_token
```

_如何获取 `token`？_ 参见 [MiService](https://github.com/Yonsm/MiService)

## 3. 使用方式

![PREVIEW](https://github.com/Yonsm/ZhiViomi/blob/main/PREVIEW.png)

如图，其中`方向`表示预约洗衣，默认时间为 `8` 点钟完成。如需修改请直接改 [fan.py](https://github.com/Yonsm/ZhiViomi/blob/main/custom_components/zhiviomi/fan.py) 中的 `DEFAULT_APPOINT_TIME = -8`，如 `-8` 表示 8 点钟，`8` 表示 8 小时后。

服务调用或自动化中也可以传入预约时间，如 `speed` 为 `program=goldenwash,dry_mode=1,appoint_clock=8`，其中 `appoint_clock` 为几点钟,`appoint_time` 为几小时候后。具体可参考[我的洗衣机自动化](https://github.com/Yonsm/.homeassistant/blob/main/automations/washer.yaml)，一键预约洗衣、烘衣，充分利用峰谷电，每天早上 8 点洗烘完成。

## 4. 参考

-   [ZhiDash](https://github.com/Yonsm/ZhiDash)
-   [Yonsm.NET](https://yonsm.github.io)
-   [Hassbian.com](https://bbs.hassbian.com/thread-12335-1-1.html)
-   [Yonsm's .homeassistant](https://github.com/Yonsm/.homeassistant)
