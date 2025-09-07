// feiniu.js - 飞牛社区自动签到脚本 (Node.js版本)
// 依赖：axios, cheerio, 青龙面板通知函数
// 环境变量：FN_COOKIE (完整的飞牛社区Cookie字符串)

const axios = require('axios');
const cheerio = require('cheerio');
const notify = require('./sendNotify'); // 青龙面板内置通知函数

// 从环境变量获取完整Cookie字符串
const fullCookieString = process.env.FN_COOKIE || '';

/**
 * 获取动态的sign参数[3](@ref)
 * @returns {Promise<string>} 动态的sign参数值
 */
async function getDynamicSign() {
    try {
        console.log('🔍 开始获取动态sign参数...');
        const response = await axios.get('https://club.fnnas.com/plugin.php?id=zqlj_sign', {
            headers: {
                'Cookie': fullCookieString,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            }
        });

        const $ = cheerio.load(response.data);
        // 尝试从签到按钮的链接中提取sign参数[3](@ref)
        const signLink = $('a.btna').attr('href');

        if (!signLink) {
            throw new Error('无法从页面中找到签到链接(可能Cookie失效或页面改版)');
        }

        const signMatch = signLink.match(/sign=([a-f0-9]+)/);
        if (signMatch && signMatch[1]) {
            console.log('✅ 动态sign参数获取成功:', signMatch[1]);
            return signMatch[1];
        } else {
            throw new Error('从签到链接中提取sign参数失败');
        }
    } catch (error) {
        console.error('❌ 获取动态sign参数失败:', error.message);
        await notify.sendNotify('飞牛签到失败', `获取动态sign参数失败: ${error.message}`);
        throw error; // 重新抛出错误，阻止后续签到执行
    }
}

/**
 * 执行签到操作
 * @param {string} dynamicSign 动态获取的sign参数
 */
async function signIn(dynamicSign) {
    try {
        const signUrl = `https://club.fnnas.com/plugin.php?id=zqlj_sign&sign=${dynamicSign}`;
        console.log('📨 发送签到请求:', signUrl);

        const response = await axios.get(signUrl, {
            headers: {
                'Cookie': fullCookieString,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            }
        });

        if (response.data.includes('恭喜您，打卡成功！')) {
            console.log('✅ 打卡成功');
            await getSignInInfo(); // 获取并推送签到详情
        } else if (response.data.includes('您今天已经打过卡了')) {
            console.log('⏰ 已经打过卡了');
            await notify.sendNotify('飞牛论坛', '您今天已经打过卡了'); // 推送已签到通知
        } else {
            // 可能的情况：Cookie失效、签到链接错误、网站改版
            const errorMsg = '打卡失败, cookies可能已经过期或站点更新.';
            console.log('❌', errorMsg);
            await notify.sendNotify('飞牛论坛', errorMsg);
        }
    } catch (error) {
        console.error('❌ 签到请求失败:', error.message);
        await notify.sendNotify('飞牛论坛', `签到请求失败: ${error.message}`);
    }
}

/**
 * 获取签到详情信息并推送[1,3](@ref)
 */
async function getSignInInfo() {
    try {
        console.log('📊 获取签到详情信息...');
        const response = await axios.get('https://club.fnnas.com/plugin.php?id=zqlj_sign', {
            headers: {
                'Cookie': fullCookieString,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            }
        });

        const $ = cheerio.load(response.data);
        const content = []; // 存储提取的签到信息

        // 定义要提取的信息项及其选择器[1](@ref)
        const patterns = [
            { name: '最近打卡', selector: 'li:contains("最近打卡")' },
            { name: '本月打卡', selector: 'li:contains("本月打卡")' },
            { name: '连续打卡', selector: 'li:contains("连续打卡")' },
            { name: '累计打卡', selector: 'li:contains("累计打卡")' },
            { name: '累计奖励', selector: 'li:contains("累计奖励")' },
            { name: '最近奖励', selector: 'li:contains("最近奖励")' },
            { name: '当前打卡等级', selector: 'li:contains("当前打卡等级")' }
        ];

        // 提取数据
        patterns.forEach(pattern => {
            const elementText = $(pattern.selector).text();
            if (elementText) {
                // 提取冒号后的值部分[3](@ref)
                const value = elementText.replace(/.*:/, '').trim(); // 注意正则表达式修改，匹配中文冒号
                content.push(`${pattern.name}: ${value}`);
            }
        });

        if (content.length > 0) {
            const message = content.join('\n');
            console.log('✅ 签到详情:\n' + message);
            // 推送签到成功及详情[1](@ref)
            await notify.sendNotify('飞牛论坛打卡成功', message);
        } else {
            throw new Error('未找到签到详情信息，页面结构可能已变更');
        }
    } catch (error) {
        console.error('❌ 获取打卡信息失败:', error.message);
        await notify.sendNotify('飞牛论坛', `获取打卡信息失败: ${error.message}`);
    }
}

/**
 * 主执行函数
 */
async function main() {
    console.log('🚀 开始执行飞牛社区自动签到任务...');
    console.log('📅 当前时间:', new Date().toLocaleString('zh-CN'));

    // 1. 检查Cookie是否配置
    if (!fullCookieString) {
        const errorMsg = '未设置环境变量 FN_COOKIE，请先在青龙面板中配置。';
        console.error('❌', errorMsg);
        await notify.sendNotify('飞牛签到配置错误', errorMsg);
        return;
    }
    console.log('✅ FN_COOKIE 环境变量已设置');

    try {
        // 2. 动态获取sign参数[3](@ref)
        const dynamicSign = await getDynamicSign();

        // 3. 执行签到
        await signIn(dynamicSign);

    } catch (error) {
        // getDynamicSign 中的错误已处理，此处捕获其他潜在错误
        console.error('❌ 任务执行过程中发生未预期错误:', error.message);
    } finally {
        console.log('🏁 任务执行完毕。');
    }
}

// 执行主函数
main();
