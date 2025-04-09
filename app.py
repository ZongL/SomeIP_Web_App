from flask import Flask, render_template, request, jsonify
from someip_midware import SomeIPMiddleware
import asyncio

app = Flask(__name__)
someip_middleware = SomeIPMiddleware()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    service_id = int(data['service'], 16)
    is_subscribed = data['subscribed']
    
    # 使用主线程的事件循环
    main_loop = someip_middleware.loop

    if is_subscribed:
        # 提交任务到主循环
        future = asyncio.run_coroutine_threadsafe(
            someip_middleware.start_periodic_subscribe(service_id, 5),
            main_loop
        )
        try:
            future.result(timeout=5)  # 等待任务启动，或捕获可能的异常
        except Exception as e:
            print(f"Error submitting task: {e}")
    else:
        # 取消订阅
        future = asyncio.run_coroutine_threadsafe(
            someip_middleware.stop_periodic_subscribe(service_id),
            main_loop
        )
        try:
            future.result(timeout=5)  # 等待任务取消，或捕获可能的异常
        except Exception as e:
            print(f"Error submitting task: {e}")


    return jsonify({'status': 'success'})

@app.route('/send_method', methods=['POST'])
def send_method():
    data = request.get_json()
    service_id = int(data['service'], 16)
    method_id = int(data['methodId'], 16)
    payload = data['payload']
    print(f"service_id: {service_id}, method_id: {method_id}, payload: {payload}")
    response = someip_middleware.send_request(service_id, method_id, payload)
    return jsonify({'response': response})

@app.route('/start_provider', methods=['POST'])
def start_provider():
    data = request.get_json()
    payload = data['payload']
    
    someip_middleware.start_service_provider(0x0303, payload)
    return jsonify({'status': 'success'})

# 修改启动部分
if __name__ == '__main__':
    # 创建专用事件循环
    middleware_loop = asyncio.new_event_loop()
    
    # 独立线程运行事件循环（您已添加的关键代码）
    import threading
    def run_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    threading.Thread(
        target=run_loop, 
        args=(middleware_loop,),
        daemon=True
    ).start()
    
    # 初始化中间件
    middleware_loop.call_soon_threadsafe(
        lambda: middleware_loop.create_task(someip_middleware.initialize())
    )
    
    # 启动Flask
    app.run(debug=False, host='0.0.0.0', port=5000)
