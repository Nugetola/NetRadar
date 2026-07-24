function Header() {
    return (
        <header className="header">
            <div>
                <div className="eyebrow">OIC NETWORK OPERATIONS</div>
                <h1>NetRadar</h1>
            </div>

            <div className="header-status">
                <span className="live-dot"></span>
                Monitoring Active
            </div>
        </header>
    );
}

export default Header;