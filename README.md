<!--
 * @Author        : fineemb
 * @Github        : https://github.com/fineemb
 * @Description   : 
 * @Date          : 2020-08-26 16:20:12
 * @LastEditors   : fineemb
 * @LastEditTime  : 2021-03-06 11:01:18
-->

# 小米云服务

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

小米云服务，支持多账号及账号下的多台设备，并为设备提供 `device_tracker` 实体。

当前版本使用小米云“查找设备”接口，支持：

- 获取设备位置、电量及更新时间
- 查找设备、设备响铃、丢失模式和云剪贴板服务
- 自有设备及家庭共享设备
- 保存 `serviceToken` / `userId`，Token 失效后使用账号密码自动刷新

## 快速上手
使用 HACS 安装，并添加自定义存储库：`https://github.com/mxyd233/xiaomi-cloud`。
![image](https://github.com/lyj0309/xiaomi-cloud/assets/50474995/e7c7fe13-db12-4167-9902-4864ce971261)
重启 Home Assistant，在“设置 → 设备与服务 → 添加集成”中搜索 `Xiaomi Cloud`，然后输入小米账号和密码。
![image](https://github.com/lyj0309/xiaomi-cloud/assets/50474995/2707f594-9af0-4b83-a4b5-111d7d9ab1c4)

稍等片刻，即可获取手机信息
## 已知问题
多设备不定时出现只能获取到一台设备的情况  
定位精度不高（可能和手机环境有关）

## 添加至地图（可选
地图，编辑，添加实体，即可把手机添加进去

## 更新

+ ### v1.0
  + 支持多设备
  + 设备查找
+ ### v1.1
  + 增加坐标类型选择
  + 增加位置刷新频率设置,单位为分钟(过高的频率会导致手机耗电严重)

+ ### v1.2
  + 增加设备发声服务
  + 增加设备丢失模式
  + 增加云剪贴板
  
+ ### v1.2.1
  + 修复数据不更新的问题

+ ### v1.2.2
  + 小米不在提供`original`坐标格式, 默认改为`baidu`坐标
  
+ ### v1.2.3
  + `original`坐标格式回归

+ ### v1.2.4
  + 修复无法登录的问题
  + 设置默认扫描间隔为60分钟 #5
    某些情况下特别是双卡用户小米会启用短信验证,导致意外的费用.所以加大默认扫描间隔, 过于频繁的请求位置也会增加电耗.
+ ### v1.2.5
  + 修复配置页面无法登录的问题
  + manifest.json增加版本号
+ ### v1.2.6
  + 不知道更新了啥
+ ### v1.2.7
  + 修复配置页面无法登录的问题

+ ### v1.2.8
  + 修复 Home Assistant 兼容性及设备追踪相关问题

+ ### v1.2.9
  + 迁移到当前小米云“查找设备”登录及设备接口
  + 支持 Token 持久化、失效后自动刷新
  + 修复自有设备和家庭共享设备的响铃、丢失模式命令
  + 修复失败的响铃、丢失模式命令被周期性重复执行的问题
    


## 服务

### `xiaomi_cloud.clipboard`
云剪贴板

| 服务属性 | 选项 | 描述|
|---------|------|----|
|`text`   | 必须 | 发送到剪贴板的文本内容|

### `xiaomi_cloud.find`
查找设备

| 服务属性 | 选项 | 描述|
|---------|------|----|
|`imei`   | 必须 | 设备的imei号,请在集成的`device_tracker`属性里查找|

### `xiaomi_cloud.noise`
设备发声

| 服务属性 | 选项 | 描述|
|---------|------|----|
|`imei`   | 必须 | 设备的imei号,请在集成的`device_tracker`属性里查找|

### `xiaomi_cloud.lost`
开启丢失模式

| 服务属性 | 选项 | 描述|
|---------|------|----|
|`imei`   | 必须 | 设备的imei号,请在集成的`device_tracker`属性里查找|
|`content`   | 必须 | 锁定设备屏幕上显示的留言|
|`phone`   | 必须 | 锁定设备屏幕上显示的手机号码|
|`onlinenotify`   | 必须 | 定位到丢失设备时，是否短信通知上面号码|

## 感谢
https://github.com/rslywhj/xiaomi-cloud
https://github.com/fineemb/xiaomi-cloud
https://github.com/lyj0309/xiaomi-cloud
