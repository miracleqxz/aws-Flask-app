

import consul
from config import Config


def check_consul():
    try:
        c = consul.Consul(
            host=Config.CONSUL_HOST,
            port=Config.CONSUL_PORT
        )
        
        
        leader = c.status.leader()
        
        
        peers = c.status.peers()
        
        
        nodes = c.catalog.nodes()[1]
        
        
        services = c.catalog.services()[1]
        
        
        datacenters = c.catalog.datacenters()
        
        
        agent_self = c.agent.self()
        agent_config = agent_self['Config']
        
        
        test_service = 'health-check-service'
        c.agent.service.register(
            name=test_service,
            service_id=test_service,
            port=9999,
            tags=['health-check', 'test'],
            check=consul.Check.tcp('localhost', 9999, '10s')
        )
        
        # Verify registration
        agent_services = c.agent.services()
        service_registered = test_service in agent_services
        
        # Get service details
        service_details = None
        if service_registered:
            service_details = {
                'id': agent_services[test_service]['ID'],
                'port': agent_services[test_service]['Port'],
                'tags': agent_services[test_service]['Tags']
            }
        
        # Deregister test service
        c.agent.service.deregister(test_service)
        
        # Health checks
        health_checks = c.agent.checks()
        total_checks = len(health_checks)
        passing_checks = sum(1 for check in health_checks.values() if check['Status'] == 'passing')
        
        return {
            'status': 'healthy',
            'service': 'consul',
            'message': 'Successfully connected to Consul',
            'details': {
                'connection': {
                    'host': Config.CONSUL_HOST,
                    'port': Config.CONSUL_PORT,
                    'datacenter': agent_config.get('Datacenter', 'N/A')
                },
                'cluster': {
                    'leader': leader,
                    'peers_count': len(peers),
                    'nodes_count': len(nodes),
                    'datacenters': datacenters
                },
                'services': {
                    'total_services': len(services),
                    'service_names': list(services.keys())
                },
                'health_checks': {
                    'total_checks': total_checks,
                    'passing_checks': passing_checks,
                    'failing_checks': total_checks - passing_checks
                },
                'agent': {
                    'version': agent_config.get('Version', 'N/A'),
                    'node_name': agent_config.get('NodeName', 'N/A'),
                    'server': agent_config.get('Server', False)
                },
                'test_result': {
                    'service_name': test_service,
                    'registration_success': service_registered,
                    'service_details': service_details,
                    'deregistration_success': True
                }
            }
        }
        
    except consul.ConsulException as e:
        return {
            'status': 'unhealthy',
            'service': 'consul',
            'message': f'Consul error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'consul',
            'message': f'Unexpected error: {str(e)}'
        }
