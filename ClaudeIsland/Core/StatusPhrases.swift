//
//  StatusPhrases.swift
//  ClaudeIsland
//
//  Context-aware status phrases for the notch header.
//  Selection considers: time of day, session count (intensity).
//  All phrases ≤5 chars to fit MacBook notch.
//

import Foundation

enum StatusPhrases {

    // MARK: - Smart Selection

    /// Pick a working phrase based on current context.
    /// 40% time-specific, 20% intensity-specific, 40% general.
    static func smartWorking(hour: Int, sessionCount: Int) -> String {
        let roll = Int.random(in: 0..<10)
        if roll < 4 {
            return timeWorking(hour: hour).randomElement() ?? general.randomElement()!
        }
        if roll < 6, sessionCount >= 2 {
            return intensity(count: sessionCount).randomElement() ?? general.randomElement()!
        }
        return general.randomElement()!
    }

    /// Pick an idle phrase based on current context.
    /// 40% time-specific, 60% general idle.
    static func smartIdle(hour: Int) -> String {
        let roll = Int.random(in: 0..<10)
        if roll < 4 {
            return timeIdle(hour: hour).randomElement() ?? idleGeneral.randomElement()!
        }
        return idleGeneral.randomElement()!
    }

    // MARK: - Time-Specific Working Phrases

    private static func timeWorking(hour: Int) -> [String] {
        switch hour {
        case 0...5:   return dawn
        case 6...8:   return earlyMorning
        case 9...11:  return morning
        case 12...13: return lunch
        case 14...17: return afternoon
        case 18...20: return evening
        case 21...23: return lateNight
        default:      return general
        }
    }

    // 凌晨 0-5
    private static let dawn: [String] = [
        "凌晨肝", "没睡呢", "通宵中", "天快亮", "夜猫子",
        "凌晨卷", "熬通宵", "不睡了", "拼通宵", "夜深了",
        "黑眼圈", "困死了", "还在肝", "凌晨冲", "星星陪",
    ]

    // 早起 6-8
    private static let earlyMorning: [String] = [
        "早安卷", "早起肝", "清晨冲", "天刚亮", "早起鸟",
        "晨间卷", "开工了", "新一天", "起床干", "早起苦",
        "赶早工", "天亮了", "清醒中", "朝气干", "打卡中",
    ]

    // 上午 9-11
    private static let morning: [String] = [
        "上午干", "早会后", "进入态", "上午冲", "精神好",
        "状态佳", "上午拼", "效率高", "干劲足", "认真干",
        "上工了", "节奏起", "开干了", "投入中", "专注中",
    ]

    // 午餐 12-13
    private static let lunch: [String] = [
        "饭都没吃", "边吃边干", "没吃饭", "饿着干", "午饭呢",
        "外卖凉", "干饭人", "吃啥呢", "饿肚子", "先干活",
        "饭后困", "想午睡", "没得吃", "工作餐", "午休?",
    ]

    // 下午 14-17
    private static let afternoon: [String] = [
        "下午困", "想下班", "还没完", "下午茶", "撑不住",
        "犯困了", "打瞌睡", "快下班", "还早呢", "熬过去",
        "下午冲", "续一杯", "醒醒干", "后半场", "倒计时",
    ]

    // 傍晚/加班 18-20
    private static let evening: [String] = [
        "又加班", "加班了", "没下班", "晚饭呢", "义务加",
        "被留了", "走不了", "OT中", "超时了", "还没走",
        "加班狗", "晚班中", "留下来", "不让走", "傍晚干",
    ]

    // 深夜 21-23
    private static let lateNight: [String] = [
        "深夜肝", "还没完", "要熬了", "夜干中", "太晚了",
        "该睡了", "睡不了", "夜猫子", "肝到秃", "月亮陪",
        "快凌晨", "深夜卷", "都这点", "停不下", "夜干活",
    ]

    // MARK: - Intensity Phrases (multi-session)

    private static func intensity(count: Int) -> [String] {
        if count >= 4 {
            return extreme
        } else {
            return busy
        }
    }

    // 2-3 sessions: busy
    private static let busy: [String] = [
        "多线程", "双开中", "并发干", "分身术", "一心二用",
        "忙翻了", "连轴转", "两头跑", "多开中", "超负荷",
    ]

    // 4+ sessions: extreme
    private static let extreme: [String] = [
        "极限了", "要爆了", "超载中", "疯了吧", "CPU满",
        "要炸了", "太多了", "满负荷", "爆满了", "崩溃边",
    ]

    // MARK: - General Working (time-independent)

    private static let general: [String] = [
        // 牛马
        "牛马中", "做牛马", "牛马!", "牛马魂", "牛马命",
        // 搬砖
        "搬砖中", "搬砖!", "猛搬砖", "搬砖王", "狂搬砖",
        // 打工
        "打工中", "打工!", "打工人", "打工魂", "打工命",
        // 卷
        "卷起来", "在卷了", "卷卷卷", "太卷了", "狂卷中",
        // 累
        "好累啊", "太难了", "累死了", "心好累", "扛不住",
        // 干活
        "干活中", "猛干活", "含泪干", "咬牙干", "拼命干",
        // 编程
        "写bug", "debug", "coding", "push中", "build",
        // 冲
        "冲冲冲", "冲鸭!", "加油干", "拼了!", "奥利给",
        // 火力
        "火力全开", "开挂中", "暴走中", "拉满了", "燃烧中",
        // 咖啡
        "续命中", "靠咖啡", "补血中", "充电中", "泡面中",
        // 表情
        "干!💪", "冲!🔥", "肝!📚", "累!😩", "拼!⚡",
        // 社畜
        "社畜中", "拉磨中", "耕地中", "老黄牛", "蜜蜂嗡",
        // 自嘲
        "穷忙族", "白干了", "瞎忙活", "不值得", "算了吧",
        // 状态
        "输出中", "处理中", "运转中", "加载中", "执行中",
        // 黑话
        "赋能中", "闭环!", "对齐中", "沉淀中", "迭代中",
        // 哲学
        "还活着", "苟活中", "挣扎中", "熬着呢", "死磕中",
    ]

    // MARK: - Time-Specific Idle Phrases

    private static func timeIdle(hour: Int) -> [String] {
        switch hour {
        case 0...5:   return idleDawn
        case 6...8:   return idleEarly
        case 9...11:  return idleMorning
        case 12...13: return idleLunch
        case 14...17: return idleAfternoon
        case 18...20: return idleEvening
        case 21...23: return idleNight
        default:      return idleGeneral
        }
    }

    private static let idleDawn: [String] = [
        "该睡了", "太晚了", "洗洗睡", "晚安~", "做梦去",
    ]
    private static let idleEarly: [String] = [
        "赖床中", "不想起", "五分钟", "再睡会", "早安~",
    ]
    private static let idleMorning: [String] = [
        "喝咖啡", "慢慢来", "还早呢", "不着急", "晒太阳",
    ]
    private static let idleLunch: [String] = [
        "吃饭去", "干饭!", "午休中", "想午睡", "饭点了",
    ]
    private static let idleAfternoon: [String] = [
        "下午茶", "快下班", "摸会鱼", "等下班", "倒计时",
    ]
    private static let idleEvening: [String] = [
        "该走了", "下班!", "溜了溜", "收工!", "回家~",
    ]
    private static let idleNight: [String] = [
        "夜宵呢", "追剧去", "该睡了", "放松下", "关电脑",
    ]

    // MARK: - General Idle (time-independent)

    private static let idleGeneral: [String] = [
        // 摸鱼
        "摸鱼中", "摸鱼!", "在摸鱼", "快乐鱼", "摸大鱼",
        "摸鱼王", "悄悄摸", "偷偷摸", "专业摸", "合法摸",
        // 划水
        "划水中", "在划水", "悄悄划", "划水王", "随便划",
        // 躺平
        "躺平了", "先躺了", "摆烂中", "躺着呢", "不干了",
        // 发呆
        "发呆中", "神游中", "放空中", "走神了", "出神中",
        // 调皮
        "等涨薪", "等下班", "想跑路", "想加薪", "想请假",
        "老板呢", "偷懒中", "带薪摸", "假装忙", "嘘~",
        // 放松
        "休息下", "喝茶中", "待机中", "省电中", "挂机中",
        "冬眠中", "歇会儿", "缓缓神", "充电中", "睡了吧",
    ]
}
