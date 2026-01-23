"""OVH mailing list client."""
import syslog
import ovh


class OVHMailingClient:
    """Client for managing OVH mailing lists."""
    
    def __init__(
        self,
        application_key: str,
        application_secret: str,
        consumer_key: str,
        domain: str,
        mailing_list_name: str,
        endpoint: str = "ovh-eu",
    ):
        """
        Initialize OVH mailing list client.
        
        Args:
            application_key: OVH application key
            application_secret: OVH application secret
            consumer_key: OVH consumer key
            domain: Domain name for the mailing list
            mailing_list_name: Name of the mailing list
            endpoint: OVH API endpoint (default: ovh-eu)
        """
        self.domain = domain
        self.mailing_list_name = mailing_list_name
        
        self.client = ovh.Client(
            endpoint=endpoint,
            application_key=application_key,
            application_secret=application_secret,
            consumer_key=consumer_key,
        )
    
    def add_subscriber(self, email: str) -> bool:
        """
        Add a subscriber to the OVH mailing list.
        
        Args:
            email: Email address to add
            
        Returns:
            True if subscriber was added or already exists, False on error
        """
        try:
            self.client.post(
                f"/email/domain/{self.domain}/mailingList/{self.mailing_list_name}/subscriber",
                email=email,
            )
            syslog.syslog(
                syslog.LOG_INFO,
                f"Successfully added {email} to mailing list",
            )
            return True
            
        except ovh.exceptions.ResourceConflictError:
            # Subscriber already exists - this is not an error
            syslog.syslog(
                syslog.LOG_INFO,
                f"Subscriber {email} already exists in mailing list",
            )
            return True
            
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to add {email} to mailing list: {e}",
            )
            return False
