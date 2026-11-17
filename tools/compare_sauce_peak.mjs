#!/usr/bin/env node
// Read-only research: print aggregates, never retained streams or identifiers.
import fs from 'node:fs';
import {loadSauce} from './run_sauce_research.mjs';

const [checkout, path, ...durations] = process.argv.slice(2);
if (!checkout || !path || !durations.length) throw new Error('Usage: node tools/compare_sauce_peak.mjs CHECKOUT STREAMS_JSON SECONDS...');
const {sauce,sha256}=loadSauce(checkout);
const streams=JSON.parse(fs.readFileSync(path));
const {time,watts}=streams;
if (!Array.isArray(time) || !Array.isArray(watts) || time.length!==watts.length || time.length<2 ||
    watts.some(x=>typeof x!=='number'||!Number.isFinite(x)||x<0) ||
    time.some((x,i)=>!Number.isFinite(x)||(i>0 && x<=time[i-1]))) throw new Error('Invalid paired time/watts');
const canInfer=Array.isArray(streams.moving) && streams.moving.length===time.length &&
    ['cadence','distance'].every(k=>streams[k]==null || (Array.isArray(streams[k]) && streams[k].length===time.length));
const variants=[['no-active-stream',{}]];
if(canInfer) variants.unshift(['inferred-active',{activeStream:sauce.data.createActiveStream(streams,{isTrainer:true})}]);
console.log(JSON.stringify({sha256,first_offset:time[0],last_offset:time.at(-1),inferred_available:canInfer}));
for(const text of durations){
    const duration=Number(text);
    if(!Number.isInteger(duration)||duration<=0) throw new Error('Durations must be positive integer seconds');
    for(const [mode,options] of variants){
        const roll=sauce.power.peakPower(duration,time,watts,options);
        if(!roll){console.log(JSON.stringify({duration,mode,result:null}));continue;}
        const values=roll.values(),times=roll.times();let zero=0,pad=0,breaks=0,added=0;
        // The first value is the rolling reference, not an integrated interval.
        for(let i=1;i<values.length;i++){
            const v=values[i];
            if(v instanceof sauce.data.Break)breaks++;
            else if(v instanceof sauce.data.Zero)zero++;
            else if(v instanceof sauce.data.Pad){pad++;added+=Number(v)*(times[i]-times[i-1]);}
        }
        console.log(JSON.stringify({duration,mode,average_watts:roll.avg(),start_offset:times[0],end_offset:times.at(-1),
            elapsed:roll.elapsed(),zero_pads:zero,value_pads:pad,break_pads:breaks,pad_watt_seconds:added}));
    }
}
