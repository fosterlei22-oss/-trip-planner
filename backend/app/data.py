from __future__ import annotations

from .models import Place

# 目的地景点库。真实场景应来自地图/POI 服务，这里用 mock 数据。
# 每城 10 个，RAG 检索才有"缩小范围"的效果。
CITY_PLACES: dict[str, list[Place]] = {
    "北京": [
        Place(name="故宫博物院", category="历史", description="适合理解北京中轴线与皇家建筑。", lat=39.9163, lng=116.3972, estimated_hours=3.5, ticket=60),
        Place(name="景山公园", category="摄影", description="俯瞰故宫全景，适合日落前后。", lat=39.9251, lng=116.3965, estimated_hours=1.5, ticket=10),
        Place(name="什刹海", category="休闲", description="胡同、湖面和小吃集中，晚上氛围好。", lat=39.9417, lng=116.3841, estimated_hours=2, ticket=0),
        Place(name="颐和园", category="历史", description="湖山园林代表，适合半日慢逛。", lat=39.9999, lng=116.2755, estimated_hours=4, ticket=30),
        Place(name="国家博物馆", category="文化", description="系统了解中国历史文化，雨天也适合。", lat=39.9051, lng=116.4011, estimated_hours=3, ticket=0),
        Place(name="南锣鼓巷", category="美食", description="胡同商业街，适合作为轻松收尾。", lat=39.9372, lng=116.4033, estimated_hours=2, ticket=0),
        Place(name="天坛公园", category="历史", description="明清皇家祭天场所，祈年殿和回音壁值得一看。", lat=39.8822, lng=116.4066, estimated_hours=2.5, ticket=15),
        Place(name="798艺术区", category="城市", description="老厂房改造的艺术区，展览和拍照打卡。", lat=39.9848, lng=116.4940, estimated_hours=3, ticket=0),
        Place(name="簋街", category="美食", description="深夜美食一条街，麻辣小龙虾和烧烤是招牌。", lat=39.9408, lng=116.4260, estimated_hours=2, ticket=0),
        Place(name="奥林匹克公园", category="城市", description="鸟巢和水立方夜景，适合散步夜拍。", lat=40.0069, lng=116.3972, estimated_hours=2, ticket=0),
    ],
    "上海": [
        Place(name="外滩", category="摄影", description="经典城市天际线，适合傍晚到夜景。", lat=31.2400, lng=121.4900, estimated_hours=1.5, ticket=0),
        Place(name="上海博物馆", category="文化", description="青铜器、书画和陶瓷收藏很强。", lat=31.2304, lng=121.4702, estimated_hours=3, ticket=0),
        Place(name="武康路", category="休闲", description="街区漫步、咖啡和历史建筑。", lat=31.2121, lng=121.4387, estimated_hours=2, ticket=0),
        Place(name="豫园", category="历史", description="江南园林和老城厢风味。", lat=31.2272, lng=121.4921, estimated_hours=2.5, ticket=40),
        Place(name="陆家嘴", category="城市", description="现代都市观景与商圈。", lat=31.2381, lng=121.4998, estimated_hours=2.5, ticket=0),
        Place(name="田子坊", category="美食", description="弄堂创意街区，适合餐饮和纪念品。", lat=31.2107, lng=121.4691, estimated_hours=2, ticket=0),
        Place(name="迪士尼度假区", category="休闲", description="主题乐园，适合亲子或成人全天游玩。", lat=31.1440, lng=121.6576, estimated_hours=8, ticket=475),
        Place(name="新天地", category="美食", description="石库门老建筑里的时尚餐饮街区。", lat=31.2206, lng=121.4751, estimated_hours=2, ticket=0),
        Place(name="上海自然博物馆", category="文化", description="恐龙化石和自然史收藏丰富，适合亲子。", lat=31.2370, lng=121.4678, estimated_hours=3, ticket=30),
        Place(name="世纪公园", category="自然", description="市区大草坪公园，适合野餐和跑步。", lat=31.2193, lng=121.5508, estimated_hours=2, ticket=10),
    ],
    "杭州": [
        Place(name="西湖苏堤", category="休闲", description="杭州最经典的湖边慢行路线。", lat=30.2444, lng=120.1436, estimated_hours=2.5, ticket=0),
        Place(name="灵隐寺", category="文化", description="寺院与飞来峰石刻，适合半日游。", lat=30.2400, lng=120.1020, estimated_hours=3, ticket=75),
        Place(name="龙井村", category="自然", description="茶园、山路和村落，适合轻徒步。", lat=30.2141, lng=120.0993, estimated_hours=2.5, ticket=0),
        Place(name="河坊街", category="美食", description="小吃、老字号和夜间逛街。", lat=30.2445, lng=120.1708, estimated_hours=2, ticket=0),
        Place(name="浙江省博物馆", category="文化", description="理解杭州历史与江南文化。", lat=30.2535, lng=120.1426, estimated_hours=2.5, ticket=0),
        Place(name="京杭大运河", category="历史", description="适合夜游或水上巴士体验。", lat=30.3149, lng=120.1432, estimated_hours=2, ticket=80),
        Place(name="西溪湿地", category="自然", description="城市湿地公园，摇橹船和水上树林。", lat=30.2686, lng=120.0590, estimated_hours=3, ticket=80),
        Place(name="宋城", category="文化", description="宋代风情主题园区，有大型演出《宋城千古情》。", lat=30.1600, lng=120.1440, estimated_hours=4, ticket=300),
        Place(name="雷峰塔", category="历史", description="西湖边的佛塔，可俯瞰西湖全景。", lat=30.2300, lng=120.1480, estimated_hours=2, ticket=40),
        Place(name="南宋御街", category="美食", description="复原南宋街市，特色小吃和老字号。", lat=30.2470, lng=120.1670, estimated_hours=2, ticket=0),
    ],
    "成都": [
        Place(name="成都大熊猫繁育研究基地", category="自然", description="建议早上去，看熊猫活动状态更好。", lat=30.7346, lng=104.1508, estimated_hours=3.5, ticket=55),
        Place(name="宽窄巷子", category="美食", description="院落街区，适合小吃和夜间散步。", lat=30.6697, lng=104.0563, estimated_hours=2, ticket=0),
        Place(name="武侯祠", category="历史", description="三国文化核心景点。", lat=30.6456, lng=104.0486, estimated_hours=2.5, ticket=50),
        Place(name="锦里", category="美食", description="与武侯祠相邻，适合晚餐和闲逛。", lat=30.6441, lng=104.0479, estimated_hours=2, ticket=0),
        Place(name="人民公园", category="休闲", description="喝盖碗茶，体验成都慢生活。", lat=30.6598, lng=104.0633, estimated_hours=1.5, ticket=0),
        Place(name="东郊记忆", category="城市", description="工业风文创街区，适合拍照。", lat=30.6714, lng=104.1272, estimated_hours=2, ticket=0),
        Place(name="杜甫草堂", category="历史", description="诗圣杜甫故居，园林和诗歌文化。", lat=30.6530, lng=104.0350, estimated_hours=2.5, ticket=50),
        Place(name="青城山", category="自然", description="道教名山，前山看道观后山更清幽。", lat=30.8970, lng=103.5780, estimated_hours=5, ticket=80),
        Place(name="太古里", category="城市", description="开放式商业街区，潮流与老建筑共存。", lat=30.6520, lng=104.0820, estimated_hours=2, ticket=0),
        Place(name="望江楼公园", category="休闲", description="临江竹文化公园，竹林品茶很惬意。", lat=30.6400, lng=104.0950, estimated_hours=1.5, ticket=0),
    ],
}

DEFAULT_PLACES = [
    Place(name="城市博物馆", category="文化", description="快速理解目的地历史和城市脉络。", lat=31.2304, lng=121.4702, estimated_hours=2.5, ticket=0),
    Place(name="老城步行街", category="美食", description="适合体验本地小吃与生活气息。", lat=31.2240, lng=121.4750, estimated_hours=2, ticket=0),
    Place(name="中心公园", category="休闲", description="安排轻松散步，缓冲行程强度。", lat=31.2200, lng=121.4600, estimated_hours=1.5, ticket=0),
    Place(name="地标观景点", category="摄影", description="适合拍摄城市天际线或夜景。", lat=31.2390, lng=121.4990, estimated_hours=2, ticket=0),
    Place(name="特色街区", category="城市", description="适合购物、咖啡和自由探索。", lat=31.2150, lng=121.4550, estimated_hours=2.5, ticket=0),
    Place(name="本地市场", category="美食", description="用半天时间感受本地饮食和市井节奏。", lat=31.2100, lng=121.4650, estimated_hours=2, ticket=0),
]
