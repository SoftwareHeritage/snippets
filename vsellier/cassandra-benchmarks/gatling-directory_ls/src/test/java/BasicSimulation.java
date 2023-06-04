import static io.gatling.javaapi.core.CoreDsl.ByteArrayBody;
import static io.gatling.javaapi.core.CoreDsl.atOnceUsers;
import static io.gatling.javaapi.core.CoreDsl.bodyLength;
import static io.gatling.javaapi.core.CoreDsl.csv;
import static io.gatling.javaapi.core.CoreDsl.feed;
import static io.gatling.javaapi.core.CoreDsl.global;
import static io.gatling.javaapi.core.CoreDsl.scenario;
import static io.gatling.javaapi.http.HttpDsl.http;

import java.io.IOException;
import java.util.HexFormat;

import org.msgpack.core.MessageBufferPacker;
import org.msgpack.core.MessagePack;

import io.gatling.javaapi.core.FeederBuilder;
import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;
import io.gatling.javaapi.http.HttpProtocolBuilder;

public class BasicSimulation extends Simulation {

	public static final String buildRequestBody(boolean recursive) {
		String body = "{ \"directory\": \"#{sha1git}\", \"recursive\": \"" + recursive + "\" }";
//		System.out.println(body);
		return body;
	}

	public static final byte[] buildDirectoryLsRequestBodyAsMsgPack(String id, boolean recursive) {
		MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
//		System.out.println(new String(id));

		try {
			packer.packMapHeader(2);
			packer.packString("directory");

			byte[] hexValue = HexFormat.of().parseHex(id);
			packer.packBinaryHeader(hexValue.length);
			packer.writePayload(hexValue);

			packer.packString("recursive");
			packer.packBoolean(recursive);
		} catch (IOException e) {
			System.err.println("Error serializing " + id);
			System.exit(1);
		}

		return packer.toByteArray();
	}

	public static final byte[] buildDirectoryGetEntriesRequestBodyAsMsgPack(String id) {
		MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
//		System.out.println(new String(id));

		try {
			packer.packMapHeader(1);
			packer.packString("directory_id");

			byte[] hexValue = HexFormat.of().parseHex(id);
			packer.packBinaryHeader(hexValue.length);
			packer.writePayload(hexValue);

		} catch (IOException e) {
			System.err.println("Error serializing " + id);
			System.exit(1);
		}

		return packer.toByteArray();
	}

	int nbUsers = Integer.getInteger("users", 10);
	long myRamp = Long.getLong("ramp", 30);
//	boolean recursive = Boolean.getBoolean("recursive");
	boolean recursive = false;
	String dataset = System.getProperty("dataset", "directory-10000-1.txt");
//	String dataset = System.getProperty("dataset", "local.txt");
//	String baseURL = System.getProperty("base_url", "http://storage1.internal.staging.swh.network:5003");
//	String baseURL = System.getProperty("base_url", "http://localhost:5002");
	String baseURL = System.getProperty("base_url", "http://storage-cassandra.internal.staging.swh.network");

	FeederBuilder<String> feeder = csv(dataset).eager().queue();

	int iterations = feeder.recordsCount();

	HttpProtocolBuilder httpProtocol = http.baseUrl(baseURL)
			.userAgentHeader("Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0")
			.contentTypeHeader("application/x-msgpack");

	ScenarioBuilder directory_ls = scenario("directory_ls").repeat(iterations / nbUsers).on(
		feed(feeder).exec(
				http("directory_ls").post("/directory/ls")
							.body(ByteArrayBody(session -> buildDirectoryLsRequestBodyAsMsgPack(
									session.getString("sha1git"), recursive)))
				.check(bodyLength().gt(2))
		)
	);

	ScenarioBuilder directory_get_entries = scenario("directory_get_entries").repeat(iterations / nbUsers)
			.on(feed(feeder).exec(http("directory_").post("/directory/get_entries")
					.body(ByteArrayBody(
							session -> buildDirectoryGetEntriesRequestBodyAsMsgPack(session.getString("sha1git"))))
					.check(bodyLength().gt(2))));

	{
		System.out.println("Loading " + iterations + " directories from " + dataset);
		System.out.println("Different users: " + nbUsers);
//		setUp(directory_get_entries.injectOpen(atOnceUsers(nbUsers)))
//				.assertions(global().failedRequests().count().is(0L))
//				.protocols(httpProtocol);

		setUp(directory_ls.injectOpen(atOnceUsers(nbUsers))).assertions(global().failedRequests().count().is(0L))
				.protocols(httpProtocol);

	}
}
