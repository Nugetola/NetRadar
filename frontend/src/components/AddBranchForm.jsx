import { useState } from "react";
import { api } from "../api/api";

function AddBranchForm({ onCreated }) {

    const [form, setForm] = useState({
        name: "",
        region: "",
        wan_gateway_ip: ""
    });

    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);

    function handleChange(event) {
        setForm({
            ...form,
            [event.target.name]: event.target.value
        });
    }

    async function handleSubmit(event) {
        event.preventDefault();

        setLoading(true);
        setMessage("");

        try {

            await api.createBranch({
                name: form.name,
                region: form.region || null,
                wan_gateway_ip: form.wan_gateway_ip || null
            });

            setMessage("Branch successfully added.");

            setForm({
                name: "",
                region: "",
                wan_gateway_ip: ""
            });

            if (onCreated) {
                onCreated();
            }

        } catch (error) {
            setMessage(error.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <form
            className="form-grid"
            onSubmit={handleSubmit}
        >

            <input
                name="name"
                placeholder="Branch Name"
                value={form.name}
                onChange={handleChange}
                required
            />

            <input
                name="region"
                placeholder="Region"
                value={form.region}
                onChange={handleChange}
            />

            <input
                name="wan_gateway_ip"
                placeholder="WAN Gateway IP"
                value={form.wan_gateway_ip}
                onChange={handleChange}
            />

            <button
                type="submit"
                disabled={loading}
            >
                {loading
                    ? "Adding..."
                    : "Add Branch"}
            </button>

            {message && (
                <p className="form-message">
                    {message}
                </p>
            )}

        </form>
    );
}

export default AddBranchForm;