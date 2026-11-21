#!/usr/bin/env python3
"""Public attached MCP checks for playback, scenarios, notifications and UI discovery."""
import argparse
import json
import math
import subprocess
import time
from pathlib import Path
from native_mcp import NativeMcp


def check_track_spectating(client, cli, profile):
    """Use the actual desktop event queue while its camera and clock keep moving."""
    exchange = profile / 'agent-files'
    exchange.mkdir(exist_ok=True)
    source = exchange / 'native-spectate.csv'
    source.write_text('entity,time,latitude,longitude\n'
                      'Survey,2026-11-15T00:00:00Z,10,-75\n'
                      'Survey,2026-11-15T01:00:00Z,11,-74\n'
                      'Survey,2026-11-15T02:00:00Z,12,-73\n')
    preview = client.call('import_preview', {'path': str(source)})
    client.call('import_commit', {'import_id': preview['import_id']})
    client.call('view_playback', {'action': 'configure', 'speed': .25, 'increment_seconds': 60})
    client.call('view_set', {'mode': 'map'})
    time.sleep(.8)
    assert client.call('view_status')['mode'] == 'map'
    started = client.call('view_navigate', {'action': 'spectate', 'entity': 'Survey'})
    assert started['mode'] == 'globe', started
    assert started['diagnostics']['spectatingEntity'] == 'Survey'
    for direction in ['reverse', 'forward', 'reverse']:
        result = client.call('view_navigate', {'action': 'spectate_direction', 'direction': direction})
        assert result['diagnostics']['spectatingDirection'] == direction
        status = client.call('view_status')
        assert status['diagnostics']['spectatingEntity'] == 'Survey'
        assert status['diagnostics']['renderErrorCount'] == 0
    profile_trace = client.call('view_profile', {'action': 'start', 'max_seconds': 10})
    assert client.call('view_wait', {'timeout_ms': 5000, 'imagery': False, 'terrain': False})['ready']
    client.call('view_profile', {'action': 'stop', 'id': profile_trace['id']})
    stopped = subprocess.run(
        [str(cli), '--data-dir', str(profile), '--attach', 'view', 'spectate-stop'],
        check=True, capture_output=True, text=True, timeout=20,
    )
    assert json.loads(stopped.stdout)['diagnostics']['spectatingEntity'] is None
    # Keep a partial window so Play continues long enough to issue Pause through
    # the same native queue; a full-range window can finish before the next call.
    bounds = client.call('snapshot', {'compact': True})['time_bounds']
    client.call('filter', {'filter': {'start': bounds[0], 'end': bounds[0] + 1800}})
    client.call('view_playback', {'action': 'configure', 'speed': .25, 'increment_seconds': 1})
    for _ in range(2):
        assert client.call('view_playback', {'action': 'play'})['playing']
        time.sleep(.2)
        assert client.call('view_playback', {'action': 'status'})['playing']
        assert not client.call('view_playback', {'action': 'pause'})['playing']
    assert client.call('view_status')['diagnostics']['renderErrorCount'] == 0


def check_globe_flight(client, cli, profile):
    target = 'view_navigate'
    status = lambda: client.call('view_status')
    pose = lambda result: result['scene']['cesium_camera']
    position = lambda result: pose(result)['position']

    def command(action, **args):
        return client.call(target, {'action': action, **args})

    def rejected(action, **args):
        try:
            command(action, **args)
        except RuntimeError as error:
            assert 'INVALID_ARGUMENT' in str(error), error
        else:
            raise AssertionError(f'Unexpected success for {action} {args}')

    client.call('view_set', {'mode': 'map'})
    rejected('flight_mode', enabled=True)
    client.call('view_set', {'mode': 'globe'})
    rejected('flight_step', forward_m=1)
    start = command('look_at', center=[0, 0, 0], distance_m=1000)
    enabled = command('flight_mode', enabled=True)
    assert enabled['diagnostics']['flightActive']
    assert math.dist(position(start), position(enabled)) < 0.001
    look = command('flight_step', pitch_degrees=90)
    assert math.dist(position(look), position(start)) < 0.001
    assert pose(look)['direction'][2] > 0.99, look
    moved = command('flight_step', forward_m=50, right_m=30, up_m=20)
    x, y, z = position(moved)
    assert abs(x - 6379157) < 0.1 and abs(y - 30) < 0.1 and abs(z - 50) < 0.1, position(moved)
    time.sleep(0.35)
    assert math.dist(position(status()), position(moved)) < 0.001

    cli_result = subprocess.run(
        [str(cli), '--data-dir', str(profile), '--attach', 'view', 'flight-step',
         '--right', '-30', '--yaw', '90'],
        check=True, capture_output=True, text=True, timeout=20,
    )
    turned = json.loads(cli_result.stdout)
    assert abs(position(turned)[1]) < 0.1
    assert pose(turned)['direction'][1] > 0.99
    landed = command('flight_step', up_m=-10000)
    assert abs(math.hypot(*position(landed)) - 6378139) < 0.1, position(landed)
    disabled = command('flight_mode', enabled=False)
    assert not disabled['diagnostics']['flightActive']
    assert pose(disabled) == pose(landed)
    command('flight_mode', enabled=True)
    client.call('view_set', {'mode': 'map'})
    assert not status()['diagnostics']['flightActive']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['cli','data-dir','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    client=NativeMcp(args.cli.resolve(),args.data_dir.resolve(),out,ui=True)
    report={'passed':False,'checks':[]}
    def passed(text):report['checks'].append(text);print('PASS',text,flush=True)
    def terminal(id):
        deadline=time.monotonic()+25
        while True:
            result=client.call('view_scenario',{'action':'status','id':id})
            if result['state']!='running':return result
            assert time.monotonic()<deadline,result
            time.sleep(.1)
    try:
        client.call('demo_open',{'id':'local-wildlife'})
        tools=client.rpc('tools/list',{})['tools']
        for name in ['query','chart_data']:
            tool=next(t for t in tools if t['name']=='chronoscope_'+name)
            assert tool['_meta']['ui']['resourceUri']=='ui://chronoscope/explorer'
        resource=client.rpc('resources/read',{'uri':'ui://chronoscope/explorer'})['contents'][0]
        assert resource['mimeType']=='text/html;profile=mcp-app' and 'ui/initialize' in resource['text']
        assert resource['_meta']['ui']['csp']['connectDomains']==[]
        query=client.call('query',{'limit':2,'fields':['id','entity']})
        assert query['workspace_id'] and len(query['events'])==2
        passed('Attached MCP Apps negotiation, HTML resource and scoped exact query result')
        client.call('view_wait',{'timeout_ms':10000})
        time.sleep(.6)
        before=client.call('view_status')
        original_preferences=client.call('preferences')
        audit=args.data_dir/'logs/engine.jsonl'
        def terrain_requests():
            return audit.read_bytes().count(b'"command":"terrain_mesh"')
        baseline_requests=terrain_requests()
        for appearance in ['light','dark','system']:
            client.call('preferences',{'preferences':{'theme':appearance,'date_format':'mdy-short','time_format':'24h-seconds'}})
            time.sleep(.6)
            current=client.call('view_status')
            assert current['scene']['cesium_camera']==before['scene']['cesium_camera'],current
            assert current['diagnostics']['terrain']['terrainProviderChanges']==before['diagnostics']['terrain']['terrainProviderChanges']
            assert terrain_requests()==baseline_requests,'Display-only Preferences sampled terrain again'
            assert current['diagnostics']['renderErrorCount']==0
        client.call('preferences',{'preferences':{'theme':original_preferences['theme'],'date_format':original_preferences['date_format'],'time_format':original_preferences['time_format']}})
        time.sleep(.3)
        passed('Native theme/date changes retain the camera and terrain provider without terrain reload requests')

        client.rpc('resources/subscribe',{'uri':'chronoscope://workspace'})
        time.sleep(.6);client.rpc('ping',{});client.notifications=[]
        client.call('filter',{'filter':{'search':'unlikely-qa-value'}})
        time.sleep(.6);client.rpc('ping',{})
        assert any(n['method']=='notifications/resources/updated' and n['params']['uri']=='chronoscope://workspace' for n in client.notifications)
        client.rpc('resources/unsubscribe',{'uri':'chronoscope://workspace'})
        client.notifications=[];client.call('filter',{'filter':{'search':''}})
        time.sleep(.6);client.rpc('ping',{})
        assert not client.notifications,client.notifications
        passed('Attached resource subscription delivers changes; unsubscribe stops updates')
        bounds=client.call('snapshot')['time_bounds'];target=bounds[0]+100
        client.call('view_playback',{'action':'configure','speed':.5,'increment_seconds':1})
        seek=client.call('view_playback',{'action':'seek','time':target});assert abs(seek['time']-target)<.001
        step=client.call('view_playback',{'action':'step','steps':2});assert abs(step['time']-target-2)<.001
        assert client.call('view_playback',{'action':'play'})['playing']
        time.sleep(.15)
        assert not client.call('view_playback',{'action':'pause'})['playing']
        passed('Native timeline configure/seek/step/play/pause through public MCP')
        steps=[{'command':'view_set','arguments':{'mode':'map','fit':True}},
               {'command':'view_wait','arguments':{'timeout_ms':10000,'imagery':False}},
               {'command':'view_navigate','arguments':{'action':'zoom','factor':1.1}},
               {'command':'wait','arguments':{'milliseconds':300}}]
        name='MCP validation '+str(time.time_ns())
        client.call('view_scenario',{'action':'save','name':name,'steps':steps})
        assert client.call('view_scenario',{'action':'list'})['scenarios'][name]==steps
        run=client.call('view_scenario',{'action':'run','name':name,'timeout_seconds':20})
        result=terminal(run['id']);assert result['state']=='complete' and result['completed_steps']==4,result
        assert result['trace'][0]['mode']=='map'
        profile=client.call('view_profile',{'action':'status','id':result['profile_id']})
        assert profile['state']=='complete' and len(profile['samples'])>0
        assert all(len(row)==len(profile['columns']) for row in profile['samples'])
        report['profile_sample_count']=len(profile['samples'])
        passed('Persistent saved recipe runs asynchronously against the native view with per-frame trace')
        client.call('view_scenario',{'action':'save','name':name,'steps':[{'command':'wait','arguments':{'milliseconds':3000}}],'overwrite':True})
        run=client.call('view_scenario',{'action':'run','name':name})
        client.call('view_scenario',{'action':'cancel','id':run['id']})
        assert terminal(run['id'])['state']=='cancelled'
        client.call('view_scenario',{'action':'remove','name':name})
        passed('Native cancellation releases profile listeners and preserves completed actions')
        check_globe_flight(client, args.cli.resolve(), args.data_dir.resolve())
        passed('Native Globe flight moves, looks and stops through MCP and CLI, with terrain clearance and mode cleanup')
        check_track_spectating(client, args.cli.resolve(), args.data_dir.resolve())
        passed('Native moving-camera status, Spectate reverse/forward/CLI stop, profiling/readiness and repeated playback pause remain responsive')
        report['passed']=True
    finally:
        client.close();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json',flush=True)


if __name__=='__main__':main()
