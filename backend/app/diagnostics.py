"""
Diagnostic Engine - NO SNMP (Clean Version)
Uses: ping, traceroute, port scan only
"""

import asyncio
import subprocess
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DiagnosticEngine:
    """
    Root Cause Diagnostic Engine for OIC NetRadar.
    Clean version - uses ping, traceroute, port scan (NO SNMP)
    """
    
    def __init__(
        self, 
        ping_count: int = 3,
        ping_timeout: int = 2
    ):
        self.ping_count = ping_count
        self.ping_timeout = ping_timeout
        
        self.common_ports = {
            22: "SSH",
            135: "NetBIOS",
            445: "SMB",
            443: "HTTPS",
            3389: "RDP",
            80: "HTTP"
        }
    
    async def run_diagnostics(self, target_ip: str) -> Dict[str, Any]:
        """Run comprehensive diagnostics on a target device."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        logger.info(f"🔍 Running diagnostics on {target_ip}")
        
        # STAGE 1: ICMP Ping
        ping_result = await self._ping(target_ip)
        
        if ping_result["success"]:
            logger.info(f"✅ {target_ip} is UP (ping successful)")
            return {
                "event_type": "DEVICE_STATUS_CHANGE",
                "timestamp": timestamp,
                "device_info": {
                    "ip_address": target_ip,
                    "status": "UP"
                },
                "diagnostics": {
                    "ping_status": "SUCCESS",
                    "failure_reason": "NONE",
                    "details": "Device is responding to ICMP ping.",
                    "root_cause_analysis": {
                        "latency_ms": ping_result.get("latency", 0),
                        "packet_loss_percent": ping_result.get("packet_loss", 0)
                    }
                },
                "impact_level": "NONE"
            }
        
        logger.warning(f"⚠️ {target_ip} is DOWN - running diagnostic sequence")
        
        # STAGE 2: Gateway Check
        gateway_result = await self._check_gateway(target_ip)
        
        # STAGE 3: Port Scan
        port_results = await self._port_scan(target_ip)
        
        # STAGE 4: Traceroute
        traceroute_result = await self._traceroute(target_ip)
        
        # Determine root cause
        failure_reason, details = self._determine_root_cause(
            ping_result, gateway_result, port_results, 
            traceroute_result, target_ip
        )
        
        diagnostic = {
            "event_type": "DEVICE_STATUS_CHANGE",
            "timestamp": timestamp,
            "device_info": {
                "ip_address": target_ip,
                "status": "DOWN"
            },
            "diagnostics": {
                "ping_status": "FAILED",
                "failure_reason": failure_reason,
                "details": details,
                "root_cause_analysis": {
                    "ping_packet_loss": ping_result.get("packet_loss", 100),
                    "gateway_reachable": gateway_result.get("reachable", False),
                    "gateway_ip": gateway_result.get("gateway_ip", "Unknown"),
                    "gateway_latency": gateway_result.get("gateway_latency", 0),
                    "responding_ports": port_results.get("responding_ports", []),
                    "any_port_responding": port_results.get("any_port_responding", False),
                    "traceroute_hops": traceroute_result.get("hops", []),
                    "traceroute_last_hop": traceroute_result.get("last_hop"),
                    "traceroute_stop_at": traceroute_result.get("stop_at")
                }
            },
            "impact_level": self._determine_impact_level(failure_reason)
        }
        
        logger.info(f"🎯 Diagnostic complete for {target_ip}: {failure_reason}")
        return diagnostic
    
    async def _ping(self, ip: str) -> Dict[str, Any]:
        """Perform ICMP ping check."""
        try:
            cmd = ['ping', '-c', str(self.ping_count), '-W', str(self.ping_timeout), '-q', ip]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=self.ping_timeout + 5
            )
            
            output = stdout.decode()
            
            if process.returncode == 0:
                loss_match = re.search(r'(\d+)% packet loss', output)
                packet_loss = int(loss_match.group(1)) if loss_match else 0
                
                latency = 0.0
                avg_match = re.search(r'= (\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)', output)
                if avg_match:
                    latency = float(avg_match.group(2))
                else:
                    time_match = re.search(r'time[=<](\d+\.?\d*)', output)
                    if time_match:
                        latency = float(time_match.group(1))
                
                return {
                    "success": True,
                    "latency": round(latency, 2),
                    "packet_loss": packet_loss
                }
            else:
                loss_match = re.search(r'(\d+)% packet loss', output)
                packet_loss = int(loss_match.group(1)) if loss_match else 100
                
                return {
                    "success": False,
                    "packet_loss": packet_loss,
                    "error": output.strip()[:200] if output else "Ping failed"
                }
                
        except asyncio.TimeoutError:
            logger.warning(f"Ping timeout for {ip}")
            return {"success": False, "packet_loss": 100, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Ping error for {ip}: {e}")
            return {"success": False, "packet_loss": 100, "error": str(e)}
    
    async def _check_gateway(self, target_ip: str) -> Dict[str, Any]:
        """Check if gateway is reachable."""
        try:
            parts = target_ip.split('.')
            if len(parts) == 4:
                gateway_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
            else:
                return {
                    "reachable": False,
                    "gateway_ip": "0.0.0.0",
                    "port_status": "UNKNOWN"
                }
            
            ping_result = await self._ping(gateway_ip)
            
            port_status = "UP (ICMP only)" if ping_result["success"] else "DOWN"
            
            return {
                "reachable": ping_result["success"],
                "gateway_ip": gateway_ip,
                "port_status": port_status,
                "gateway_latency": ping_result.get("latency", 0)
            }
            
        except Exception as e:
            logger.error(f"Gateway check error for {target_ip}: {e}")
            return {
                "reachable": False,
                "gateway_ip": "0.0.0.0",
                "port_status": "UNKNOWN"
            }
    
    async def _port_scan(self, target_ip: str) -> Dict[str, Any]:
        """Scan common ports to check if device is responding."""
        responding_ports = []
        
        async def check_port(port: int) -> Optional[int]:
            try:
                conn = asyncio.open_connection(target_ip, port)
                reader, writer = await asyncio.wait_for(conn, timeout=2.0)
                writer.close()
                await writer.wait_closed()
                return port
            except:
                return None
        
        tasks = [check_port(port) for port in self.common_ports.keys()]
        results = await asyncio.gather(*tasks)
        
        responding_ports = [port for port in results if port is not None]
        
        port_names = []
        for port in responding_ports:
            if port in self.common_ports:
                port_names.append({
                    "port": port,
                    "service": self.common_ports[port]
                })
        
        logger.debug(f"Port scan on {target_ip}: Responding ports: {port_names}")
        
        return {
            "responding_ports": port_names,
            "any_port_responding": len(responding_ports) > 0
        }
    
    async def _traceroute(self, target_ip: str, max_hops: int = 15) -> Dict[str, Any]:
        """Perform traceroute to identify where path fails."""
        try:
            cmd = ['traceroute', '-n', '-m', str(max_hops), '-w', '2', '-q', '1', target_ip]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            hops = []
            
            if process.returncode == 0:
                output = stdout.decode()
                
                for line in output.split('\n'):
                    match = re.match(r'\s*(\d+)\s+([\d.]+|\*)\s+([\d.]+)?', line.strip())
                    if match:
                        hop_num = int(match.group(1))
                        hop_ip = match.group(2)
                        if hop_ip != '*':
                            hops.append({"hop": hop_num, "ip": hop_ip})
                        else:
                            hops.append({"hop": hop_num, "ip": "*"})
                
                reached_target = target_ip in [h["ip"] for h in hops if h["ip"] != "*"]
                
                last_reachable = None
                for h in reversed(hops):
                    if h["ip"] != "*":
                        last_reachable = h["ip"]
                        break
                
                stop_at = None
                if not reached_target and last_reachable:
                    stop_at = last_reachable
                
                return {
                    "hops": hops,
                    "last_hop": last_reachable,
                    "stop_at": stop_at,
                    "reached_target": reached_target
                }
            
            return {
                "hops": [],
                "last_hop": None,
                "stop_at": target_ip,
                "reached_target": False,
                "error": stderr.decode()[:100] if stderr else "Traceroute failed"
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Traceroute timeout for {target_ip}")
            return {"hops": [], "last_hop": None, "stop_at": target_ip, "reached_target": False}
        except Exception as e:
            logger.error(f"Traceroute error for {target_ip}: {e}")
            return {"hops": [], "last_hop": None, "stop_at": target_ip, "reached_target": False}
    
    def _determine_root_cause(
        self,
        ping: Dict,
        gateway: Dict,
        ports: Dict,
        traceroute: Dict,
        target_ip: str
    ) -> Tuple[str, str]:
        """Determine root cause based on all diagnostic data."""
        
        if not gateway["reachable"]:
            return (
                "VLAN_GATEWAY_DOWN",
                f"VLAN gateway ({gateway.get('gateway_ip', 'Unknown')}) is unreachable."
            )
        
        if ports["any_port_responding"] and not ping["success"]:
            return (
                "ICMP_BLOCKED",
                f"Device {target_ip} is operational but ICMP is blocked."
            )
        
        if ping.get("packet_loss", 0) > 50:
            return (
                "NETWORK_CONGESTION",
                f"High packet loss ({ping.get('packet_loss')}%) detected."
            )
        
        if traceroute.get("stop_at") and traceroute["stop_at"] != target_ip:
            return (
                "LINK_FAILURE",
                f"Network path fails at {traceroute['stop_at']}."
            )
        
        if traceroute.get("reached_target") and not ping["success"]:
            return (
                "DEVICE_UNRESPONSIVE",
                f"Device {target_ip} is reachable but not responding to ICMP."
            )
        
        if not ping["success"] and not ports["any_port_responding"]:
            return (
                "CABLE_FAILURE",
                f"Device {target_ip} is completely unresponsive."
            )
        
        return (
            "UNKNOWN_FAILURE",
            f"Device {target_ip} is down but root cause unknown."
        )
    
    def _determine_impact_level(self, failure_reason: str) -> str:
        critical_failures = ["VLAN_GATEWAY_DOWN", "CABLE_FAILURE", "LINK_FAILURE"]
        high_failures = ["DEVICE_UNRESPONSIVE", "NETWORK_CONGESTION"]
        
        if failure_reason in critical_failures:
            return "CRITICAL"
        elif failure_reason in high_failures:
            return "HIGH"
        elif failure_reason == "ICMP_BLOCKED":
            return "MEDIUM"
        else:
            return "LOW"